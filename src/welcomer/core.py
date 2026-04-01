"""Core welcomer logic."""

from __future__ import annotations

from dataclasses import dataclass

from .config import WelcomerConfig
from .ical import Recipient


@dataclass
class WelcomeResult:
    recipient: str
    email: str
    subject: str
    body: str
    dry_run: bool


def _render(template: str, recipient: Recipient) -> str:
    ctx = {
        "name": recipient.name,
        "email": recipient.email,
        "start": str(recipient.start or ""),
        "end": str(recipient.end or ""),
        **recipient.extra,
    }
    return template.format_map(ctx)


def build_welcomes(
    config: WelcomerConfig,
    recipients: list[Recipient],
    dry_run: bool = False,
) -> list[WelcomeResult]:
    return [
        WelcomeResult(
            recipient=recipient.name,
            email=recipient.email,
            subject=_render(config.subject, recipient),
            body=_render(config.body, recipient),
            dry_run=dry_run,
        )
        for recipient in recipients
    ]
