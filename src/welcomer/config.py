"""Config loading for welcomer."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RecipientConfig:
    name: str
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class WelcomerConfig:
    title: str = "Welcome"
    message: str = "Hello, {name}!"
    footer: str = ""
    recipients: list[RecipientConfig] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "WelcomerConfig":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WelcomerConfig":
        recipients = [
            RecipientConfig(
                name=r["name"],
                tags=r.get("tags", []),
                extra={k: v for k, v in r.items() if k not in ("name", "tags")},
            )
            for r in data.get("recipients", [])
        ]
        return cls(
            title=data.get("title", "Welcome"),
            message=data.get("message", "Hello, {name}!"),
            footer=data.get("footer", ""),
            recipients=recipients,
            channels=data.get("channels", []),
            raw=data,
        )


DEFAULT_CONFIG_PATH = Path("config.toml")
EXAMPLE_CONFIG_PATH = Path("config.example.toml")
