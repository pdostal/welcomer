"""CLI entry point for welcomer."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .config import DEFAULT_CONFIG_PATH, EXAMPLE_CONFIG_PATH, WelcomerConfig
from .core import build_welcomes

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
@click.option(
    "--title",
    default=None,
    help="Override the welcome title from config.",
)
@click.option(
    "--message",
    "-m",
    default=None,
    help="Override the welcome message template from config.",
)
@click.option(
    "--recipient",
    "-r",
    multiple=True,
    help="Add recipient name(s) on the fly (repeatable).",
)
@click.option(
    "--channel",
    multiple=True,
    help="Override channels (repeatable).",
)
@click.version_option()
def main(
    config: Path | None,
    dry_run: bool,
    title: str | None,
    message: str | None,
    recipient: tuple[str, ...],
    channel: tuple[str, ...],
) -> None:
    """Send configurable welcome messages to recipients across channels.

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

    # Apply CLI overrides
    if title:
        cfg.title = title
    if message:
        cfg.message = message
    if channel:
        cfg.channels = list(channel)
    if recipient:
        from .config import RecipientConfig
        extra = [RecipientConfig(name=n) for n in recipient]
        cfg.recipients = cfg.recipients + extra

    if not cfg.recipients:
        console.print("[yellow]No recipients configured. Add some in config.toml or use --recipient.[/]")
        raise SystemExit(0)

    results = build_welcomes(cfg, dry_run=dry_run)

    # Render title + optional header markdown
    header_md = cfg.raw.get("header_markdown", "")
    console.print()
    console.print(Panel(f"[bold]{cfg.title}[/bold]", expand=False))
    if header_md:
        console.print(Markdown(header_md))
    console.print()

    if dry_run:
        console.print("[bold yellow]DRY RUN[/bold yellow] — nothing will be sent.\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Recipient")
    table.add_column("Channel")
    table.add_column("Message")

    for r in results:
        table.add_row(r.recipient, r.channel, r.rendered_message)

    console.print(table)

    if cfg.footer:
        console.print()
        console.print(Markdown(cfg.footer))

    if not dry_run:
        console.print(f"\n[green]Sent {len(results)} welcome message(s).[/green]")
    else:
        console.print(f"\n[yellow]Would send {len(results)} welcome message(s).[/yellow]")
