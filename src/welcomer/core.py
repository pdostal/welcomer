"""Core welcomer logic."""

from __future__ import annotations

from dataclasses import dataclass

import jinja2

from .config import WelcomerConfig
from .ical import Recipient

# Shared Jinja2 environment for all template rendering.
# autoescape=False  — emails are plain text, not HTML.
# undefined         — accessing an undefined variable renders as empty string.
# keep_trailing_newline — preserve intentional trailing newlines in body templates.
_env = jinja2.Environment(
    autoescape=False,
    undefined=jinja2.Undefined,
    keep_trailing_newline=True,
)


@dataclass
class WelcomeResult:
    recipient: str
    email: str
    subject: str
    body: str
    dry_run: bool


def _render(template: str, recipient: Recipient) -> str:
    """Render a Jinja2 template string with the recipient's context variables.

    Available variables: name, email, phone, start, end, adults, kids,
    property, official_name, provider, summary, plus any extra fields.

    ``official_name`` falls back to ``property`` when not set.
    ``adults`` and ``kids`` are integers (or empty string when unknown).
    ``phone`` is an empty string when unknown; use ``{{ phone or "N/A" }}``
    or ``{% if phone %}`` in the template as needed.
    """
    ctx: dict = {
        "name": recipient.name,
        "email": recipient.email or "",
        "phone": recipient.phone or "",
        "start": str(recipient.start or ""),
        "end": str(recipient.end or ""),
        "adults": "" if recipient.adults is None else recipient.adults,
        "kids": "" if recipient.kids is None else recipient.kids,
        "property": "",
        "official_name": "",
        "provider": "",
        "summary": "",
        **recipient.extra,
    }
    # official_name falls back to property when not explicitly set
    if not ctx["official_name"]:
        ctx["official_name"] = ctx["property"]
    return _env.from_string(template).render(ctx)


def build_welcomes(
    config: WelcomerConfig,
    recipients: list[Recipient],
    dry_run: bool = False,
) -> list[WelcomeResult]:
    message_map = {message.name: message for message in config.messages}
    default_message = message_map.get("default") or next(iter(message_map.values()), None)
    if default_message is None:
        raise ValueError("no messages configured")
    results = []
    for recipient in recipients:
        # Recipients inherit the calendar's message; tests that call this directly
        # fall back to the default message.
        message = message_map.get(recipient.extra.get("message", ""), default_message)
        results.append(
            WelcomeResult(
                recipient=recipient.name,
                email=recipient.email,
                subject=_render(message.subject, recipient),
                body=_render(message.body, recipient),
                dry_run=dry_run,
            )
        )
    return results
