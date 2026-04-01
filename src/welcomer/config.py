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


@dataclass
class WelcomerConfig:
    subject: str = "Welcome"
    body: str = "Hello, {name}!"
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
            CalendarConfig(url=c["url"], name=c.get("name", "")) for c in data.get("calendars", [])
        ]
        return cls(
            subject=data.get("subject", "Welcome"),
            body=data.get("body", "Hello, {name}!"),
            calendars=calendars,
            raw=data,
        )


DEFAULT_CONFIG_PATH = Path("config.toml")
EXAMPLE_CONFIG_PATH = Path("config.example.toml")
