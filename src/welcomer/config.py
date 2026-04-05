"""Config loading for welcomer."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CalendarConfig:
    url: str
    name: str = ""
    provider: str = ""


@dataclass
class SmtpConfig:
    host: str = "localhost"
    port: int = 1025
    from_addr: str = ""
    username: str = ""
    password: str = ""
    tls: bool = False
    ssl: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmtpConfig:
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 1025),
            from_addr=data.get("from", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
            tls=data.get("tls", False),
            ssl=data.get("ssl", False),
        )


@dataclass
class WelcomerConfig:
    subject: str = "Welcome"
    body: str = "Hello, {name}!"
    date_format: str = "%Y-%m-%d"
    days: int | None = None
    advance: int = 14
    smtp: SmtpConfig | None = None
    calendars: list[CalendarConfig] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> WelcomerConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WelcomerConfig:
        calendars = [
            CalendarConfig(url=c["url"], name=c.get("name", ""), provider=c.get("provider", ""))
            for c in data.get("calendars", [])
        ]
        smtp_data = data.get("smtp")
        return cls(
            subject=data.get("subject", "Welcome"),
            body=data.get("body", "Hello, {name}!"),
            date_format=data.get("date_format", "%Y-%m-%d"),
            days=data.get("days"),
            advance=data.get("advance", 14),
            smtp=SmtpConfig.from_dict(smtp_data) if smtp_data is not None else None,
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
