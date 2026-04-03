"""CLI entry point for welcomer."""

from __future__ import annotations

import importlib.resources
import tomllib
from datetime import date, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from .config import (
    EXAMPLE_CONFIG_PATH,
    LOCAL_CONFIG_PATH,
    XDG_CONFIG_PATH,
    WelcomerConfig,
    find_default_config,
)
from .core import build_welcomes
from .ical import Recipient, fetch_recipients, recipients_from_ical

console = Console()


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


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Path to config file. Defaults to config.toml if it exists,"
        " otherwise ~/.config/welcomer.toml."
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
    help="Only show reservations starting within this many days from today.",
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
    property_filter: str | None,
    provider_filter: str | None,
    days: int | None,
    print_note: bool,
) -> None:
    """Send configurable welcome messages loaded from iCal calendar URLs.

    Reads configuration from a TOML file. Looks for config.toml in the current
    directory first, then falls back to ~/.config/welcomer.toml.
    Copy config.example.toml to either location and edit to get started.
    """
    if test_config and not dry_run:
        raise click.UsageError("--test-config requires --dry-run")

    recipients = []

    if test_config:
        data_pkg = importlib.resources.files("welcomer.data")
        toml_bytes = data_pkg.joinpath("test_config.toml").read_bytes()
        cfg = WelcomerConfig.from_dict(tomllib.loads(toml_bytes.decode()))
        calendars = _apply_filters(cfg.calendars, property_filter, provider_filter)
        for cal in calendars:
            label = cal.name or cal.url
            found = _load_calendar(cal.url, Path.cwd())
            for r in found:
                r.extra["property"] = cal.name
                r.extra["provider"] = cal.provider
            provider_str = f" · {cal.provider}" if cal.provider else ""
            console.print(f"[dim]Loaded {len(found)} recipient(s) from {label}{provider_str}[/dim]")
            recipients.extend(found)
    else:
        config_path = config or find_default_config()

        if not config_path.exists():
            if EXAMPLE_CONFIG_PATH.exists():
                console.print(
                    f"[yellow]Config file not found:[/] {config_path}\n"
                    f"[dim]Copy config.example.toml to {LOCAL_CONFIG_PATH}"
                    f" or {XDG_CONFIG_PATH} and edit it.[/]"
                )
            else:
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

        for cal in _apply_filters(cfg.calendars, property_filter, provider_filter):
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

    if days is not None:
        today = date.today()
        cutoff = today + timedelta(days=days)
        recipients = [rec for rec in recipients if rec.start and today <= rec.start <= cutoff]

    if not recipients:
        console.print("[yellow]No recipients found in any calendar.[/]")
        raise SystemExit(0)

    results = build_welcomes(cfg, recipients, dry_run=dry_run)

    # Pre-compute plain-text column values for width alignment
    rows = []
    for r, rec in zip(results, recipients, strict=True):
        phone = rec.phone or "unknown"
        start = rec.start.strftime(cfg.date_format) if rec.start else ""
        end = rec.end.strftime(cfg.date_format) if rec.end else ""
        prop = rec.extra.get("property", "")
        provider = rec.extra.get("provider", "")
        duration = f"{(rec.end - rec.start).days} days" if rec.start and rec.end else ""
        prop_sep = " · " if prop and provider else ""
        prop_col = f"{prop}{prop_sep}{provider}"
        rows.append(
            (
                r.recipient,
                start,
                end,
                duration,
                prop_col,
                r.email,
                phone,
                r,
                prop,
                provider,
                rec.start,
                rec.end,
            )
        )

    rows.sort(key=lambda row: (row[10] or date.max, row[11] or date.max, row[8], row[9]))

    w_name = max(max(len(row[0]) for row in rows), len("👤 Name") + 1)
    w_from = max(max(len(row[1]) for row in rows), len("📅 From") + 1)
    w_to = max(max(len(row[2]) for row in rows), len("🏁 To") + 1)
    w_dur = max(max(len(row[3]) for row in rows), len("⏳ Duration") + 1)
    w_prop = max(max(len(row[4]) for row in rows), len("🏡 Calendar") + 1)
    w_email = max(max(len(row[5]) for row in rows), len("📧 E-mail") + 1)

    console.print(
        f"[bold dim]"
        f"{'👤 Name':<{w_name - 1}}  "
        f"{'📅 From':<{w_from - 1}}  "
        f"{'🏁 To':<{w_to - 1}}  "
        f"{'⏳ Duration':<{w_dur - 1}}  "
        f"{'🏡 Calendar':<{w_prop - 1}}  "
        f"{'📧 E-mail':<{w_email - 1}}  "
        f"📞 Phone"
        f"[/bold dim]"
    )

    for name, start, end, duration, prop_col, email, phone, r, *_ in rows:
        console.print(
            f"[bold green]{name:<{w_name}}[/bold green]"
            f"  [cyan]{start:<{w_from}}[/cyan]"
            f"  [cyan]{end:<{w_to}}[/cyan]"
            f"  [cyan]{duration:<{w_dur}}[/cyan]"
            f"  {prop_col:<{w_prop}}"
            f"  [blue]{email:<{w_email}}[/blue]"
            f"  {phone}"
        )
        if print_note:
            console.print(f"  [yellow]{r.subject}[/yellow]")
            console.print(Markdown(r.body))

    count_color = "yellow" if dry_run else "green"
    verb = "Would send" if dry_run else "Sent"
    console.print(f"[{count_color}]{verb} {len(results)} message(s).[/{count_color}]")
