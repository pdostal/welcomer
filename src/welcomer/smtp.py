"""SMTP email sending."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from .config import SmtpConfig


def send_email(cfg: SmtpConfig, to: str, subject: str, body: str) -> None:
    """Send a plain-text email via SMTP.

    Uses SSL when ``cfg.ssl`` is True (port 465 style).
    Uses STARTTLS when ``cfg.tls`` is True.
    Authenticates only when ``cfg.username`` is set.
    """
    msg = EmailMessage()
    msg["From"] = cfg.from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if cfg.ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.host, cfg.port, context=context) as s:
            if cfg.username:
                s.login(cfg.username, cfg.password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg.host, cfg.port) as s:
            if cfg.tls:
                s.starttls()
            if cfg.username:
                s.login(cfg.username, cfg.password)
            s.send_message(msg)
