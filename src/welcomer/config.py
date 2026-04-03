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
class WelcomerConfig:
    subject: str = "Welcome"
    body: str = "Hello, {name}!"
    date_format: str = "%Y-%m-%d"
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
        return cls(
            subject=data.get("subject", "Welcome"),
            body=data.get("body", "Hello, {name}!"),
            date_format=data.get("date_format", "%Y-%m-%d"),
            calendars=calendars,
            raw=data,
        )


LOCAL_CONFIG_PATH = Path("config.toml")
XDG_CONFIG_PATH = Path.home() / ".config" / "welcomer.toml"
EXAMPLE_CONFIG_PATH = Path("config.example.toml")


def find_default_config() -> Path:
    """Return the default config path.

    Local config.toml takes priority, then ~/.config/welcomer.toml.
    """
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    return XDG_CONFIG_PATH
