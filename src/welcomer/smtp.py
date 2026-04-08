"""SMTP email sending."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from .config import SmtpConfig


def _smtp_send(cfg: SmtpConfig, msg: EmailMessage, envelope: list[str]) -> None:
    """Dispatch a pre-built message via plain SMTP or SSL."""
    if cfg.ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.host, cfg.port, context=context) as s:
            if cfg.username:
                s.login(cfg.username, cfg.password)
            s.send_message(msg, to_addrs=envelope)
    else:
        with smtplib.SMTP(cfg.host, cfg.port) as s:
            if cfg.tls:
                s.starttls()
            if cfg.username:
                s.login(cfg.username, cfg.password)
            s.send_message(msg, to_addrs=envelope)


def send_email(cfg: SmtpConfig, to: str, subject: str, body: str) -> None:
    """Send a plain-text email via SMTP.

    ``to`` may be empty when ``send_without_email`` is active; in that case the
    message is addressed only to CC/BCC recipients (no ``To`` header is set).

    Uses SSL when ``cfg.ssl`` is True (port 465 style).
    Uses STARTTLS when ``cfg.tls`` is True.
    Authenticates only when ``cfg.username`` is set.
    Formats the ``From`` header as ``"from_name <from_addr>"`` when ``cfg.from_name``
    is set; otherwise uses ``cfg.from_addr`` directly (which may itself contain a
    display name in ``"Name <email>"`` format).
    CC addresses appear in the message headers; BCC addresses are included in the
    SMTP envelope only and never written to the message headers.
    """
    msg = EmailMessage()
    from_header = f"{cfg.from_name} <{cfg.from_addr}>" if cfg.from_name else cfg.from_addr
    msg["From"] = from_header
    if to:
        msg["To"] = to
    if cfg.cc:
        msg["CC"] = ", ".join(cfg.cc)
    msg["Subject"] = subject
    msg.set_content(body)

    # Build envelope: To (if present) + CC (already in headers) + BCC (envelope only)
    envelope: list[str] = ([to] if to else []) + cfg.cc + cfg.bcc
    if not envelope:
        return  # nothing to send — skip silently

    _smtp_send(cfg, msg, envelope)
