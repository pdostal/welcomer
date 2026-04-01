"""Core welcomer logic."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RecipientConfig, WelcomerConfig


@dataclass
class WelcomeResult:
    recipient: str
    channel: str
    rendered_message: str
    dry_run: bool


def render_message(template: str, recipient: RecipientConfig) -> str:
    """Render a message template for a recipient."""
    ctx = {"name": recipient.name, **recipient.extra}
    return template.format_map(ctx)


def build_welcomes(config: WelcomerConfig, dry_run: bool = False) -> list[WelcomeResult]:
    """Build welcome results for all recipients and channels."""
    results: list[WelcomeResult] = []
    channels = config.channels if config.channels else ["default"]

    for recipient in config.recipients:
        active_channels = recipient.tags if recipient.tags else channels
        for channel in active_channels:
            if channel not in channels and channel not in recipient.tags:
                continue
            rendered = render_message(config.message, recipient)
            results.append(
                WelcomeResult(
                    recipient=recipient.name,
                    channel=channel,
                    rendered_message=rendered,
                    dry_run=dry_run,
                )
            )

    return results
