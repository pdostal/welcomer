"""Config loading for welcomer."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CalendarConfig:
    url: str
    property: str = ""  # accommodation/property name
    official_name: str = ""  # official/legal property name for templates
    provider: str = ""
    message: str = ""


@dataclass
class MessageConfig:
    name: str
    subject: str
    body: str


@dataclass
class SmtpConfig:
    host: str = "localhost"
    port: int = 1025
    from_addr: str = ""
    from_name: str = ""  # display name — formatted as "from_name <from_addr>"
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    username: str = ""
    password: str = ""
    tls: bool = False
    ssl: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmtpConfig:
        def _as_list(val: Any) -> list[str]:
            if val is None:
                return []
            if isinstance(val, str):
                return [val]
            return list(val)

        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 1025),
            from_addr=data.get("from", ""),
            from_name=data.get("from_name", ""),
            cc=_as_list(data.get("cc")),
            bcc=_as_list(data.get("bcc")),
            username=data.get("username", ""),
            password=data.get("password", ""),
            tls=data.get("tls", False),
            ssl=data.get("ssl", False),
        )


@dataclass
class WelcomerConfig:
    date_format: str = "%Y-%m-%d"
    days: int | None = None
    advance: int = 14
    send_without_email: bool = False
    smtp: SmtpConfig | None = None
    messages: list[MessageConfig] = field(default_factory=list)
    calendars: list[CalendarConfig] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> WelcomerConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WelcomerConfig:
        if "subject" in data or "body" in data:
            raise ValueError("top-level subject/body are no longer supported")
        if "calendars" in data:
            raise ValueError("[[calendars]] is no longer supported; use [[calendar]]")

        messages = []
        for m in data.get("message", []):
            name = m.get("name", "")
            if not name:
                raise ValueError("message name is required")
            subject = m.get("subject", "")
            body = m.get("body", "")
            if not subject or not body:
                raise ValueError(f"message '{name}' requires subject and body")
            messages.append(MessageConfig(name=name, subject=subject, body=body))

        message_names = {m.name for m in messages}
        calendars = []
        for c in data.get("calendar", []):
            message = c.get("message", "")
            if not message:
                raise ValueError("calendar message is required")
            if message not in message_names:
                raise ValueError(f"unknown message: {message}")
            calendars.append(
                CalendarConfig(
                    url=c["url"],
                    # Accept "property" key; fall back to "name" for backward compat
                    property=c.get("property", c.get("name", "")),
                    official_name=c.get("official_name", ""),
                    provider=c.get("provider", ""),
                    message=message,
                )
            )
        smtp_data = data.get("smtp")
        return cls(
            date_format=data.get("date_format", "%Y-%m-%d"),
            days=data.get("days"),
            advance=data.get("advance", 14),
            send_without_email=data.get("send_without_email", False),
            smtp=SmtpConfig.from_dict(smtp_data) if smtp_data is not None else None,
            messages=messages,
            calendars=calendars,
            raw=data,
        )


LOCAL_CONFIG_PATH = Path("config.toml")
XDG_CONFIG_PATH = Path.home() / ".config" / "welcomer" / "config.toml"
SENT_LOG_PATH = Path.home() / ".config" / "welcomer" / "sent.log"
CACHE_DIR = Path.home() / ".config" / "welcomer" / "cache"


def find_default_config() -> Path:
    """Return the default config path.

    Local config.toml takes priority, then ~/.config/welcomer/config.toml.
    """
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    return XDG_CONFIG_PATH
