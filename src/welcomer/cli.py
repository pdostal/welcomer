"""CLI entry point for welcomer."""

from __future__ import annotations

import importlib.resources
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
from .ical import fetch_recipients, recipients_from_ical

console = Console()


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
    "--test-calendar",
    is_flag=True,
    default=False,
    help="Use the bundled test calendar instead of configured URLs. Requires --dry-run.",
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
    test_calendar: bool,
    print_note: bool,
) -> None:
    """Send configurable welcome messages loaded from iCal calendar URLs.

    Reads configuration from a TOML file. Looks for config.toml in the current
    directory first, then falls back to ~/.config/welcomer.toml.
    Copy config.example.toml to either location and edit to get started.
    """
    if test_calendar and not dry_run:
        raise click.UsageError("--test-calendar requires --dry-run")

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

    recipients = []
    if test_calendar:
        data = importlib.resources.files("welcomer.data").joinpath("cal.ics").read_bytes()
        recipients = recipients_from_ical(data)
        console.print(f"[dim]Loaded {len(recipients)} recipient(s) from test calendar[/dim]")
    else:
        for cal in cfg.calendars:
            label = cal.name or cal.url
            try:
                found = fetch_recipients(cal.url)
                console.print(f"[dim]Loaded {len(found)} recipient(s) from {label}[/dim]")
                recipients.extend(found)
            except Exception as e:
                console.print(f"[red]Failed to load {label}:[/red] {e}")

    if not recipients:
        console.print("[yellow]No recipients found in any calendar.[/]")
        raise SystemExit(0)

    results = build_welcomes(cfg, recipients, dry_run=dry_run)

    for r, rec in zip(results, recipients, strict=True):
        phone = rec.phone or "[dim]unknown[/dim]"
        dates = (
            f"[cyan]{rec.start}[/cyan] – [cyan]{rec.end}[/cyan]"
            if rec.start or rec.end
            else "[dim]unknown[/dim]"
        )
        console.print(
            f"[bold green]{r.recipient}[/bold green]  {dates}  [blue]{r.email}[/blue]  {phone}"
        )
        if print_note:
            console.print(f"  [yellow]{r.subject}[/yellow]")
            console.print(Markdown(r.body))

    count_color = "yellow" if dry_run else "green"
    verb = "Would send" if dry_run else "Sent"
    console.print(f"[{count_color}]{verb} {len(results)} message(s).[/{count_color}]")
