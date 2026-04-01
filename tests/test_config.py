"""Tests for config loading."""

import pytest

from welcomer.config import WelcomerConfig


SAMPLE = {
    "title": "Hello World",
    "message": "Hi {name}!",
    "footer": "Bye.",
    "channels": ["#test"],
    "recipients": [
        {"name": "Alice", "tags": ["#test"]},
        {"name": "Bob", "role": "admin"},
    ],
}


def test_from_dict_basic():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert cfg.title == "Hello World"
    assert cfg.message == "Hi {name}!"
    assert cfg.channels == ["#test"]
    assert len(cfg.recipients) == 2


def test_recipients_parsed():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    alice = cfg.recipients[0]
    assert alice.name == "Alice"
    assert alice.tags == ["#test"]

    bob = cfg.recipients[1]
    assert bob.name == "Bob"
    assert bob.extra["role"] == "admin"


def test_defaults():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.title == "Welcome"
    assert cfg.message == "Hello, {name}!"
    assert cfg.recipients == []
    assert cfg.channels == []


def test_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[project]\ntitle = "Test"\n\ntitle = "Loaded"\nmessage = "Hey {name}"\n\n'
        '[[recipients]]\nname = "Dave"\n',
        encoding="utf-8",
    )
    # write a valid toml
    toml.write_text(
        'title = "Loaded"\nmessage = "Hey {name}"\n\n[[recipients]]\nname = "Dave"\n',
        encoding="utf-8",
    )
    cfg = WelcomerConfig.from_file(toml)
    assert cfg.title == "Loaded"
    assert cfg.recipients[0].name == "Dave"
