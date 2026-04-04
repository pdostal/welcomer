"""CLI entry point for welcomer."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from .config import (
    LOCAL_CONFIG_PATH,
    SENT_LOG_PATH,
    XDG_CONFIG_PATH,
    WelcomerConfig,
    find_default_config,
)
from .core import build_welcomes
from .ical import Recipient, fetch_recipients, recipients_from_ical

console = Console()


def _detect_overlaps(recipients: list[Recipient]) -> list[tuple[Recipient, Recipient]]:
    """Return pairs with the same property whose date ranges overlap."""
    by_property: dict[str, list[Recipient]] = {}
    for rec in recipients:
        prop = rec.extra.get("property", "")
        if prop and rec.start and rec.end:
            by_property.setdefault(prop, []).append(rec)
    overlaps = []
    for recs in by_property.values():
        for i, a in enumerate(recs):
            for b in recs[i + 1 :]:
                if a.start < b.end and b.start < a.end:
                    overlaps.append((a, b))
    return overlaps


def _apply_filters(calendars, property_filter, provider_filter):
    if property_filter:
        calendars = [c for c in calendars if property_filter.lower() in c.name.lower()]
    if provider_filter:
        calendars = [c for c in calendars if provider_filter.lower() in c.provider.lower()]
    return calendars


def _load_calendar(url: str, base_dir: Path) -> list[Recipient]:
    """Load recipients from a URL, absolute path, or relative path.

    Relative paths are resolved against base_dir (the config file's directory).
    """
    if url.startswith(("http://", "https://")):
        return fetch_recipients(url)
    path = Path(url)
    if not path.is_absolute():
        path = base_dir / path
    return recipients_from_ical(path.read_bytes())


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


def _sent_marker(email: str, already_sent: bool, eligible: bool) -> str:
    """Return a Rich-markup sent-status cell, always 4 visible chars wide.

    ✗  red    — no email address, cannot send
    ✓  green  — already sent (in sent.log)
    ●  green  — eligible to send now (start ≤ today + advance days), not yet sent
    ○  yellow — not yet eligible (check-in too far in the future)
    """
    if email == "none":
        return "[red]✗   [/red]"
    if already_sent:
        return "[green]✓   [/green]"
    if eligible:
        return "[green]●   [/green]"
    return "[yellow]○   [/yellow]"


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
) -> None:
    """Send configurable welcome messages loaded from iCal calendar URLs.

    Reads configuration from a TOML file. Looks for config.toml in the current
    directory first, then falls back to ~/.config/welcomer/config.toml.
    Copy the example from README.md to either location and edit to get started.
    """
    if test_config and not dry_run:
        raise click.UsageError("--test-config requires --dry-run")

    sent_keys = _load_sent_log(SENT_LOG_PATH)
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
            if (not property_filter or property_filter.lower() in cal.name.lower())
            and (not provider_filter or provider_filter.lower() in cal.provider.lower())
        ]
        for cal, recs in sorted(filtered, key=lambda x: x[0].name):
            for r in recs:
                r.extra["property"] = cal.name
                r.extra["provider"] = cal.provider
            provider_str = f" · {cal.provider}" if cal.provider else ""
            console.print(
                f"[dim]Loaded {len(recs)} recipient(s) from {cal.name}{provider_str}[/dim]"
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
            key=lambda c: c.name,
        ):
            label = cal.name or cal.url
            try:
                found = _load_calendar(cal.url, config_path.parent)
                for r in found:
                    r.extra["property"] = cal.name
                    r.extra["provider"] = cal.provider
                provider_str = f" · {cal.provider}" if cal.provider else ""
                console.print(
                    f"[dim]Loaded {len(found)} recipient(s) from {label}{provider_str}[/dim]"
                )
                recipients.extend(found)
            except Exception as e:
                console.print(f"[red]Failed to load {label}:[/red] {e}")

    today = date.today()

    effective_days = days if days is not None else cfg.days
    if effective_days is not None:
        cutoff = today + timedelta(days=effective_days)
        recipients = [rec for rec in recipients if rec.start and today <= rec.start <= cutoff]

    effective_advance = advance if advance is not None else cfg.advance

    overlaps = _detect_overlaps(recipients)
    overlapping_recipients: set[int] = set()

    for a, b in overlaps:
        prop = a.extra.get("property", "")
        a_prov = a.extra.get("provider", "")
        b_prov = b.extra.get("provider", "")
        overlapping_recipients.add(id(a))
        overlapping_recipients.add(id(b))
        console.print(
            f"[bold red]⚠ Overlap at {prop}:[/bold red] "
            f"[red]{a.name} ({a_prov}, {a.start}–{a.end})"
            f" × {b.name} ({b_prov}, {b.start}–{b.end})[/red]"
        )

    if not recipients:
        console.print("[yellow]No recipients found in any calendar.[/]")
        raise SystemExit(0)

    results = build_welcomes(cfg, recipients, dry_run=dry_run)

    # Pre-compute plain-text column values for width alignment
    rows = []
    for r, rec in zip(results, recipients, strict=True):
        phone = rec.phone or "none"
        start = rec.start.strftime(cfg.date_format) if rec.start else ""
        end = rec.end.strftime(cfg.date_format) if rec.end else ""
        prop = rec.extra.get("property", "")
        provider = rec.extra.get("provider", "")
        duration = f"{(rec.end - rec.start).days} days" if rec.start and rec.end else ""
        prop_sep = " · " if prop and provider else ""
        prop_col = f"{prop}{prop_sep}{provider}"
        eligible = rec.start is not None and rec.start <= today + timedelta(days=effective_advance)
        display_name = "Reservation" if r.recipient == "CLOSED - Not available" else r.recipient
        rows.append(
            (
                display_name,
                start,
                end,
                duration,
                prop_col,
                r.email or "none",
                phone,
                r,
                prop,
                provider,
                rec.start,
                rec.end,
                rec,
                eligible,
            )
        )

    rows.sort(key=lambda row: (row[10] or date.max, row[11] or date.max, row[8], row[9]))

    _dates = [f"{r[1]} → {r[2]}" if r[1] and r[2] else r[1] or r[2] or "" for r in rows]
    w_name = max(max(len(row[0]) for row in rows), len("👤 Name") + 1)
    w_date = max(max(len(d) for d in _dates), len("📅 Date") + 1)
    w_dur = max(max(len(row[3]) for row in rows), len("⏳") + 1)
    w_prop = max(max(len(row[4]) for row in rows), len("🏡 Calendar") + 1)
    w_email = max(max(len(row[5]) for row in rows), len("📧 E-mail") + 1)

    console.print(
        f"[bold dim]"
        f"{'👤 Name':<{w_name - 1}}  "
        f"{'📅 Date':<{w_date - 1}}  "
        f"{'⏳':<{w_dur - 1}}  "
        f"{'✉️':<4}  "
        f"{'🏡 Calendar':<{w_prop - 1}}  "
        f"{'📧 E-mail':<{w_email - 1}}  "
        f"📞 Phone"
        f"[/bold dim]"
    )

    for (
        name,
        start,
        end,
        duration,
        prop_col,
        email,
        phone,
        r,
        _prop,
        _prov,
        _start,
        _end,
        rec,
        eligible,
    ) in rows:
        date_color = "red" if id(rec) in overlapping_recipients else "cyan"
        already_sent = _sent_key(rec, _prop) in sent_keys
        date_col = f"{start} → {end}" if start and end else start or end or ""
        console.print(
            f"[bold green]{name:<{w_name}}[/bold green]"
            f"  [{date_color}]{date_col:<{w_date}}[/{date_color}]"
            f"  [{date_color}]{duration:<{w_dur}}[/{date_color}]"
            f"  {_sent_marker(email, already_sent, eligible)}"
            f"  {prop_col:<{w_prop}}"
            f"  [blue]{email:<{w_email}}[/blue]"
            f"  {phone}"
        )
        if print_note:
            console.print(f"  [yellow]{r.subject}[/yellow]")
            console.print(Markdown(r.body))

    if test_config:
        sent_count = sum(1 for r in results if r.email)
        console.print(f"[yellow]Would send {sent_count} message(s).[/yellow]")
    elif yes:
        confirmed = 0
        for (
            _name,
            _start_str,
            _end_str,
            _dur,
            _pcol,
            email,
            _phone,
            _r,
            _prop,
            _prov,
            _start,
            _end,
            rec,
            eligible,
        ) in rows:
            if email == "none":
                continue
            if not eligible:
                continue
            key = _sent_key(rec, _prop)
            if key in sent_keys:
                continue
            if not dry_run:
                _append_sent_log(SENT_LOG_PATH, key)
                sent_keys.add(key)
            confirmed += 1
        color = "yellow" if dry_run else "green"
        verb = "Would send" if dry_run else "Sent"
        console.print(f"[{color}]{verb} {confirmed} message(s).[/{color}]")
    else:
        console.print()
        confirmed = 0
        for (
            name,
            start,
            end,
            _dur,
            _pcol,
            email,
            _phone,
            _r,
            _prop,
            _prov,
            _start,
            _end,
            rec,
            eligible,
        ) in rows:
            if email == "none":
                continue
            if not eligible:
                continue
            key = _sent_key(rec, _prop)
            if key in sent_keys:
                continue
            date_str = f" ({start} → {end})" if start else ""
            prop_str = f" at {_prop}" if _prop else ""
            if click.confirm(f"Send to {name} ({email}){prop_str}{date_str}?", default=False):
                if not dry_run:
                    _append_sent_log(SENT_LOG_PATH, key)
                    sent_keys.add(key)
                confirmed += 1
        color = "yellow" if dry_run else "green"
        verb = "Would send" if dry_run else "Sent"
        console.print(f"[{color}]{verb} {confirmed} message(s) interactively.[/{color}]")
