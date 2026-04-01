"""CLI entry point for welcomer."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from .config import DEFAULT_CONFIG_PATH, EXAMPLE_CONFIG_PATH, WelcomerConfig
from .core import build_welcomes
from .ical import fetch_recipients

console = Console()


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file (default: config.toml).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be sent without actually sending.",
)
@click.version_option()
def main(
    config: Path | None,
    dry_run: bool,
) -> None:
    """Send configurable welcome messages loaded from iCal calendar URLs.

    Reads configuration from a TOML file (config.toml by default).
    Copy config.example.toml to config.toml and edit to get started.
    """
    config_path = config or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        if EXAMPLE_CONFIG_PATH.exists():
            console.print(
                f"[yellow]Config file not found:[/] {config_path}\n"
                f"[dim]Copy config.example.toml to config.toml and edit it.[/]"
            )
        else:
            console.print(f"[red]Config file not found:[/] {config_path}")
        raise SystemExit(1)

    cfg = WelcomerConfig.from_file(config_path)

    if not cfg.calendars:
        console.print(
            "[yellow]No calendars configured. Add [[calendars]] entries in config.toml.[/]"
        )
        raise SystemExit(0)

    recipients = []
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

    dry_tag = " [yellow](dry run)[/yellow]" if dry_run else ""

    for r in results:
        console.print(f"\n[bold cyan]{r.subject}[/bold cyan]{dry_tag}")
        console.print(f"[dim]To: {r.recipient} <{r.email}>[/dim]")
        console.print(Markdown(r.body))

    count_color = "yellow" if dry_run else "green"
    verb = "Would send" if dry_run else "Sent"
    console.print(f"[{count_color}]{verb} {len(results)} message(s).[/{count_color}]")
