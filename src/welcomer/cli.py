"""CLI entry point for welcomer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

from .config import (
    LOCAL_CONFIG_PATH,
    SENT_LOG_PATH,
    XDG_CONFIG_PATH,
    SmtpConfig,
    WelcomerConfig,
    find_default_config,
)
from .core import WelcomeResult, build_welcomes
from .ical import Recipient, fetch_recipients, recipients_from_ical
from .smtp import send_email

console = Console()


def _detect_overlaps(
    recipients: list[Recipient],
) -> list[tuple[Recipient, Recipient, str]]:
    """Return (a, b, overlapping_property) triples for date-range overlaps.

    Multi-property (merged) recipients are expanded into each constituent property
    bucket.  The third element of each triple is the property bucket where the
    overlap was detected — used to show the specific property name in the warning
    rather than the generic "Multi" label.
    """
    by_property: dict[str, list[Recipient]] = {}
    for rec in recipients:
        if not rec.start or not rec.end:
            continue
        prop = rec.extra.get("property", "")
        # Multi entries store constituent props in "properties"; fall back to [prop].
        constituent = rec.extra.get("properties") or ([prop] if prop else [])
        for p in constituent:
            by_property.setdefault(p, []).append(rec)
    overlaps = []
    seen: set[tuple[int, int]] = set()
    for bucket_prop, recs in by_property.items():
        for i, a in enumerate(recs):
            for b in recs[i + 1 :]:
                if a.start < b.end and b.start < a.end:
                    pair = (min(id(a), id(b)), max(id(a), id(b)))
                    if pair not in seen:
                        seen.add(pair)
                        overlaps.append((a, b, bucket_prop))
    return overlaps


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _name_color(start: date | None, end: date | None, today: date) -> str:
    """Return 'blue' for active-today reservations, 'green' for all others.

    Active-today means: check-in today, currently ongoing, or check-out today.
    """
    if start is not None and end is not None and start <= today <= end:
        return "blue"
    return "green"


def _merge_multi_property(recipients: list[Recipient]) -> list[Recipient]:
    """Collapse same-provider, same-name, exact-date recipients across different properties.

    When the same guest appears in two or more calendars from the same booking provider
    (different properties, identical check-in and check-out dates), merge them into a
    single entry with ``extra["property"] = "Multi"``. This prevents duplicate emails.
    """
    n = len(recipients)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = recipients[i], recipients[j]
            prov_i = ri.extra.get("provider", "")
            prov_j = rj.extra.get("provider", "")
            if not prov_i or prov_i != prov_j:
                continue
            prop_i = ri.extra.get("property", "")
            prop_j = rj.extra.get("property", "")
            if prop_i == prop_j:
                continue
            if _normalize_name(ri.name) != _normalize_name(rj.name):
                continue
            if ri.start != rj.start or ri.end != rj.end:
                continue
            union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    skip: set[int] = set()
    replacements: dict[int, Recipient] = {}

    for _root, indices in clusters.items():
        if len(indices) < 2:
            continue
        props = {recipients[i].extra.get("property", "") for i in indices}
        if len(props) < 2:
            continue
        base = recipients[indices[0]]
        starts = [recipients[i].start for i in indices if recipients[i].start]
        ends = [recipients[i].end for i in indices if recipients[i].end]
        email = base.email or next(
            (recipients[i].email for i in indices if recipients[i].email), None
        )
        phone = base.phone or next(
            (recipients[i].phone for i in indices if recipients[i].phone), ""
        )
        # Build property → official_name mapping; fall back to property name when not set.
        prop_to_official: dict[str, str] = {
            recipients[i].extra.get("property", ""): (
                recipients[i].extra.get("official_name", "")
                or recipients[i].extra.get("property", "")
            )
            for i in indices
        }
        sorted_props = sorted(props)
        official_name = ", ".join(prop_to_official.get(p, p) for p in sorted_props)
        merged = Recipient(
            name=base.name,
            email=email,
            phone=phone,
            adults=base.adults,
            kids=base.kids,
            start=min(starts) if starts else base.start,
            end=max(ends) if ends else base.end,
            extra={
                **base.extra,
                "property": "Multi",
                "properties": sorted_props,
                "official_name": official_name,
            },
        )
        replacements[indices[0]] = merged
        for i in indices[1:]:
            skip.add(i)

    result = []
    for i, rec in enumerate(recipients):
        if i in skip:
            continue
        result.append(replacements.get(i, rec))
    return result


def _apply_filters(calendars, property_filter, provider_filter):
    if property_filter:
        calendars = [c for c in calendars if property_filter.lower() in c.property.lower()]
    if provider_filter:
        calendars = [c for c in calendars if provider_filter.lower() in c.provider.lower()]
    return calendars


def _load_calendar(
    url: str, base_dir: Path, force_refresh: bool = False
) -> tuple[list[Recipient], bool]:
    """Load recipients from a URL, absolute path, or relative path.

    Returns ``(recipients, from_cache)`` where ``from_cache`` is True when the
    data was served from the 5-hour disk cache.  Always False for local paths.
    Remote URLs are cached for 5 hours; pass force_refresh=True to bypass.
    """
    if url.startswith(("http://", "https://")):
        from .cache import get_cached

        from_cache = not force_refresh and get_cached(url) is not None
        return fetch_recipients(url, force_refresh=force_refresh), from_cache
    path = Path(url)
    if not path.is_absolute():
        path = base_dir / path
    return recipients_from_ical(path.read_bytes()), False


def _sent_key(rec: Recipient, prop: str) -> str:
    return f"{prop}|{rec.start}|{rec.end}|{rec.name}|{rec.email or ''}"


def _load_sent_log(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(path.read_text(encoding="utf-8").splitlines())


def _append_sent_log(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def _sent_marker(
    email: str,
    already_sent: bool,
    eligible: bool,
    past_checkin: bool,
    send_without_email: bool = False,
) -> str:
    """Return a Rich-markup sent-status cell, always 4 visible chars wide.

    ✓  green  — already sent (in sent.log)
    ●  green  — eligible to send now (today ≤ check-in ≤ today + advance days)
    ○  yellow — not yet eligible; only shown when ``send_without_email`` is True
    (empty)   — no actionable status

    ``○`` is only displayed when ``send_without_email`` is True, because that is the
    only mode where not-yet-eligible reservations without a direct email address are
    still destined to be sent (to CC/BCC). In the default mode (send_without_email=False)
    showing ``○`` would be misleading — nothing will be sent to those rows.
    ``●`` is shown whenever a recipient has an email address and is within the eligibility
    window, regardless of ``send_without_email``.
    """
    if already_sent:
        return "[green]✓   [/green]"
    if past_checkin:
        return "    "
    if eligible and (email or send_without_email):
        return "[green]●   [/green]"
    if not eligible and (email or send_without_email):
        return "[yellow]○   [/yellow]"
    return "    "


@dataclass
class _TableRow:
    display_name: str
    start_str: str
    end_str: str
    duration_str: str
    prop_col: str
    email: str
    phone: str
    guests_str: str
    result: WelcomeResult
    prop: str
    prov: str
    start: date | None
    end: date | None
    recipient: Recipient
    eligible: bool
    past_checkin: bool


def _build_table_rows(
    results: list[WelcomeResult],
    recipients: list[Recipient],
    cfg: WelcomerConfig,
    today: date,
    effective_advance: int,
) -> list[_TableRow]:
    rows = []
    for r, rec in zip(results, recipients, strict=True):
        prop = rec.extra.get("property", "")
        prov = rec.extra.get("provider", "")
        start_str = rec.start.strftime(cfg.date_format) if rec.start else ""
        end_str = rec.end.strftime(cfg.date_format) if rec.end else ""
        duration_str = f"{(rec.end - rec.start).days} days" if rec.start and rec.end else ""
        prop_col = f"{prop} · {prov}" if prop and prov else prop or prov
        past_checkin = rec.start is not None and rec.start < today
        eligible = rec.start is not None and today <= rec.start <= today + timedelta(
            days=effective_advance
        )
        display_name = "Reservation" if r.recipient == "CLOSED - Not available" else r.recipient
        adults_str = f"{rec.adults} adults" if rec.adults else ""
        kids_str = f"{rec.kids} kids" if rec.kids else ""
        guests_str = ", ".join(x for x in (adults_str, kids_str) if x)
        rows.append(
            _TableRow(
                display_name=display_name,
                start_str=start_str,
                end_str=end_str,
                duration_str=duration_str,
                prop_col=prop_col,
                email=r.email or "",
                phone=(rec.phone or "").replace(" ", ""),
                guests_str=guests_str,
                result=r,
                prop=prop,
                prov=prov,
                start=rec.start,
                end=rec.end,
                recipient=rec,
                eligible=eligible,
                past_checkin=past_checkin,
            )
        )
    rows.sort(key=lambda row: (row.start or date.max, row.end or date.max, row.prop, row.prov))
    return rows


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Path to config file. Defaults to config.toml if it exists,"
        " otherwise ~/.config/welcomer/config.toml."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be sent without actually sending.",
)
@click.option(
    "--test-config",
    is_flag=True,
    default=False,
    help=("Use the bundled test config and calendars instead of real ones. Requires --dry-run."),
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help=(
        "Auto-send all eligible welcome emails without prompting."
        " Skips already-sent reservations and records sends in ~/.config/welcomer/sent.log."
        " Use --dry-run to preview what would be sent."
    ),
)
@click.option(
    "--property",
    "property_filter",
    default=None,
    help="Only process calendars whose property name contains this string (case-insensitive).",
)
@click.option(
    "--provider",
    "provider_filter",
    default=None,
    help="Only process calendars whose provider name contains this string (case-insensitive).",
)
@click.option(
    "--days",
    type=int,
    default=None,
    help=(
        "Only show reservations starting within this many days from today."
        " Overrides the days setting in the config file."
    ),
)
@click.option(
    "--advance",
    type=int,
    default=None,
    help=(
        "Days before check-in when a reservation becomes eligible to send (default: 14)."
        " Overrides the advance setting in the config file."
    ),
)
@click.option(
    "--print-note",
    is_flag=True,
    default=False,
    help="Also print the rendered subject and message body for each recipient.",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    default=False,
    help=(
        "Bypass the 5-hour calendar cache and re-fetch all remote URLs."
        " Has no effect on local file paths or --test-config."
    ),
)
@click.option(
    "--silent",
    "-s",
    is_flag=True,
    default=False,
    help="Suppress 'Loaded N event(s)' and send-count summary lines.",
)
@click.version_option()
def main(
    config: Path | None,
    dry_run: bool,
    test_config: bool,
    yes: bool,
    property_filter: str | None,
    provider_filter: str | None,
    days: int | None,
    advance: int | None,
    print_note: bool,
    force_refresh: bool,
    silent: bool,
) -> None:
    """Send configurable welcome messages loaded from iCal calendar URLs.

    Reads configuration from a TOML file. Looks for config.toml in the current
    directory first, then falls back to ~/.config/welcomer/config.toml.
    Copy the example from README.md to either location and edit to get started.
    """
    if test_config and not dry_run:
        raise click.UsageError("--test-config requires --dry-run")

    sent_keys = _load_sent_log(SENT_LOG_PATH)
    if not silent:
        if test_config:
            console.print("[dim]Sent log: test mode, 1 entry pre-seeded[/dim]")
        elif SENT_LOG_PATH.exists():
            console.print(f"[dim]Sent log: {SENT_LOG_PATH} ({len(sent_keys)} entries)[/dim]")
        else:
            console.print(f"[dim]Sent log will be created at: {SENT_LOG_PATH}[/dim]")

    recipients = []

    if test_config:
        from .data.testdata import TEST_CONFIG, get_pre_sent_key, get_test_calendars

        cfg = TEST_CONFIG
        sent_keys.add(get_pre_sent_key())
        all_calendars = get_test_calendars()
        filtered = [
            (cal, recs)
            for cal, recs in all_calendars
            if (not property_filter or property_filter.lower() in cal.property.lower())
            and (not provider_filter or provider_filter.lower() in cal.provider.lower())
        ]
        for cal, recs in sorted(filtered, key=lambda x: x[0].property):
            for r in recs:
                r.extra["property"] = cal.property
                r.extra["official_name"] = cal.official_name
                r.extra["provider"] = cal.provider
            provider_str = f" · {cal.provider}" if cal.provider else ""
            if not silent:
                console.print(
                    f"[dim]Loaded {len(recs)} event(s) from {cal.property}{provider_str}[/dim]"
                )
            recipients.extend(recs)
    else:
        config_path = config or find_default_config()

        if not config_path.exists():
            console.print(
                f"[red]Config file not found:[/] {config_path}\n"
                f"[dim]Expected {LOCAL_CONFIG_PATH} or {XDG_CONFIG_PATH}.[/]"
            )
            raise SystemExit(1)

        cfg = WelcomerConfig.from_file(config_path)

        if not cfg.calendars:
            console.print(
                "[yellow]No calendars configured. Add [[calendars]] entries in config.toml.[/]"
            )
            raise SystemExit(0)

        for cal in sorted(
            _apply_filters(cfg.calendars, property_filter, provider_filter),
            key=lambda c: c.property,
        ):
            label = cal.property or cal.url
            try:
                found, from_cache = _load_calendar(
                    cal.url, config_path.parent, force_refresh=force_refresh
                )
                for r in found:
                    r.extra["property"] = cal.property
                    r.extra["official_name"] = cal.official_name
                    r.extra["provider"] = cal.provider
                provider_str = f" · {cal.provider}" if cal.provider else ""
                cache_str = " (cached)" if from_cache else ""
                if not silent:
                    console.print(
                        f"[dim]Loaded {len(found)} event(s) from "
                        f"{label}{provider_str}{cache_str}[/dim]"
                    )
                recipients.extend(found)
            except Exception as e:
                console.print(f"[red]Failed to load {label}:[/red] {e}")

    today = date.today()

    # Merge same-provider, same-name guests that appear in multiple properties
    # into a single "Multi" entry to avoid duplicate emails.
    recipients = _merge_multi_property(recipients)

    # Detect overlaps across ALL loaded events before any day-window filter,
    # so warnings appear even when overlapping reservations fall outside --days.
    overlaps = _detect_overlaps(recipients)

    # Always hide reservations that ended before today (checkout yesterday or earlier).
    # Reservations with no end date are kept. Checkout-today (end == today) is kept.
    recipients = [rec for rec in recipients if rec.end is None or rec.end >= today]

    effective_days = days if days is not None else cfg.days
    if effective_days is not None:
        cutoff = today + timedelta(days=effective_days)
        recipients = [
            rec for rec in recipients if rec.start and rec.start <= cutoff and rec.end is not None
        ]

    effective_advance = advance if advance is not None else cfg.advance
    overlapping_recipients: set[int] = set()

    for a, b, _overlap_prop in overlaps:
        a_prop = a.extra.get("property", "")
        b_prop = b.extra.get("property", "")
        a_prov = a.extra.get("provider", "")
        b_prov = b.extra.get("provider", "")
        a_cal = f"{a_prop} · {a_prov}" if a_prov else a_prop
        b_cal = f"{b_prop} · {b_prov}" if b_prov else b_prop
        overlapping_recipients.add(id(a))
        overlapping_recipients.add(id(b))
        console.print(
            f"[bold red]⚠ Overlap:[/bold red] "
            f"[red]{a.name} ({a_cal}, {a.start} → {a.end})"
            f" × {b.name} ({b_cal}, {b.start} → {b.end})[/red]"
        )

    if not recipients:
        console.print("[yellow]No recipients found in any calendar.[/]")
        raise SystemExit(0)

    results = build_welcomes(cfg, recipients, dry_run=dry_run)
    rows = _build_table_rows(results, recipients, cfg, today, effective_advance)

    send_without_email = cfg.send_without_email

    show_guests = any(row.guests_str for row in rows)

    _dates = [
        f"{r.start_str} → {r.end_str}" if r.start_str and r.end_str else r.start_str or r.end_str
        for r in rows
    ]
    w_name = max(max(len(row.display_name) for row in rows), len("👤 Name") + 1)
    w_date = max(max(len(d) for d in _dates), len("📅 Date") + 1)
    w_dur = max(max(len(row.duration_str) for row in rows), len("⏳") + 1)
    w_prop = max(max(len(row.prop_col) for row in rows), len("🏡 Property") + 1)
    w_email = max(max(len(row.email) for row in rows), len("📧 E-mail") + 1)
    # Phone needs a fixed width when guests are shown so the guests column aligns.
    w_phone = max(max(len(row.phone) for row in rows), len("📞 Phone")) if show_guests else 0
    # +2 compensates for the double-width 👥 emoji so data values align under the label.
    w_guests = (
        max(max(len(row.guests_str) for row in rows), len("Guests") + 1) + 2 if show_guests else 0
    )

    header = (
        f"[bold dim]"
        f"{'👤 Name':<{w_name - 1}}  "
        f"{'📅 Date':<{w_date - 1}}  "
        f"{'⏳':<{w_dur - 1}}  "
        f"{'✉️':<4}  "
        f"{'🏡 Property':<{w_prop - 1}}  "
        f"{'📧 E-mail':<{w_email - 1}}  "
    )
    if show_guests:
        header += f"{'📞 Phone':<{w_phone - 1}}  {'👥 Guests':<{w_guests - 2}}"
    else:
        header += "📞 Phone"
    header += "[/bold dim]"
    console.print(header)

    for row in rows:
        date_color = "red" if id(row.recipient) in overlapping_recipients else "cyan"
        already_sent = _sent_key(row.recipient, row.prop) in sent_keys
        date_col = (
            f"{row.start_str} → {row.end_str}"
            if row.start_str and row.end_str
            else row.start_str or row.end_str or ""
        )
        name_color = _name_color(row.start, row.end, today)
        marker = _sent_marker(
            row.email, already_sent, row.eligible, row.past_checkin, send_without_email
        )
        line = (
            f"[bold {name_color}]{row.display_name:<{w_name}}[/bold {name_color}]"
            f"  [{date_color}]{date_col:<{w_date}}[/{date_color}]"
            f"  [{date_color}]{row.duration_str:<{w_dur}}[/{date_color}]"
            f"  {marker}"
            f"  {row.prop_col:<{w_prop}}"
            f"  [bold blue]{escape(row.email):<{w_email}}[/bold blue]"
        )
        if show_guests:
            line += (
                f"  [bold green]{escape(row.phone):<{w_phone}}[/bold green]"
                f"  [dim]{escape(row.guests_str):<{w_guests}}[/dim]"
            )
        else:
            line += f"  [bold green]{escape(row.phone)}[/bold green]"
        console.print(line)
        if print_note:
            console.print(f"  [yellow]{row.result.subject}[/yellow]")
            console.print(Markdown(row.result.body))

    if not dry_run and not test_config and cfg.smtp is None:
        console.print(
            "[yellow]Warning: no [smtp] section in config — emails will not be sent.[/yellow]"
        )

    def _do_send(smtp_cfg: SmtpConfig | None, result: WelcomeResult, email_addr: str) -> bool:
        """Attempt to send one email. Returns True on success."""
        if smtp_cfg is None:
            return False
        try:
            send_email(smtp_cfg, email_addr, result.subject, result.body)
            return True
        except Exception as exc:
            console.print(f"[red]Failed to send to {email_addr or '(no address)'}: {exc}[/red]")
            return False

    def _row_has_dest(row: _TableRow) -> bool:
        """True when there is somewhere to send the email."""
        return bool(row.email) or (
            send_without_email and cfg.smtp is not None and bool(cfg.smtp.cc or cfg.smtp.bcc)
        )

    if test_config:
        sent_count = sum(1 for row in rows if row.eligible and _row_has_dest(row))
        if not silent:
            console.print(f"[yellow]Would send {sent_count} message(s).[/yellow]")
    elif yes or dry_run:
        confirmed = 0
        for row in rows:
            if not _row_has_dest(row):
                continue
            if not row.eligible:
                continue
            key = _sent_key(row.recipient, row.prop)
            if key in sent_keys:
                continue
            if not dry_run:
                if not _do_send(cfg.smtp, row.result, row.email):
                    continue
                _append_sent_log(SENT_LOG_PATH, key)
                sent_keys.add(key)
            confirmed += 1
        color = "yellow" if dry_run else "green"
        verb = "Would send" if dry_run else "Sent"
        if not silent:
            console.print(f"[{color}]{verb} {confirmed} message(s).[/{color}]")
    else:
        console.print()
        confirmed = 0
        for row in rows:
            if not row.eligible:
                continue
            key = _sent_key(row.recipient, row.prop)
            if key in sent_keys:
                continue

            rec = row.recipient
            email = rec.email or ""
            phone = rec.phone or ""

            # Prompt for missing contact details before rendering the email,
            # since {email} and {phone} may appear in the subject/body template.
            if not email:
                val = click.prompt(
                    f"Email for {row.display_name}" + (f" at {row.prop}" if row.prop else ""),
                    default="",
                    show_default=False,
                ).strip()
                email = val

            if not rec.phone:
                val = click.prompt(
                    f"Phone for {row.display_name}",
                    default="",
                    show_default=False,
                ).strip()
                phone = val

            # Re-render subject/body if contact data was filled in by the user.
            result = row.result
            if email != (rec.email or "") or phone != (rec.phone or ""):
                updated_rec = Recipient(
                    name=rec.name,
                    email=email or None,
                    phone=phone,
                    adults=rec.adults,
                    kids=rec.kids,
                    start=rec.start,
                    end=rec.end,
                    extra=rec.extra,
                )
                result = build_welcomes(cfg, [updated_rec])[0]

            # Check there is somewhere to deliver the email after prompting.
            has_dest = bool(email) or (
                send_without_email and cfg.smtp is not None and bool(cfg.smtp.cc or cfg.smtp.bcc)
            )
            if not has_dest:
                continue

            date_str = f" ({row.start_str} → {row.end_str})" if row.start_str else ""
            prop_str = f" at {row.prop}" if row.prop else ""
            dest_str = email if email else "(no email — sending to CC/BCC)"
            if click.confirm(
                f"Send to {row.display_name} ({dest_str}){prop_str}{date_str}?", default=False
            ):
                if not dry_run:
                    if not _do_send(cfg.smtp, result, email):
                        continue
                    _append_sent_log(SENT_LOG_PATH, key)
                    sent_keys.add(key)
                confirmed += 1
        color = "yellow" if dry_run else "green"
        verb = "Would send" if dry_run else "Sent"
        if not silent:
            console.print(f"[{color}]{verb} {confirmed} message(s) interactively.[/{color}]")
