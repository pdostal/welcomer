"""Tests for core welcomer logic."""

import pytest

from welcomer.config import RecipientConfig, WelcomerConfig
from welcomer.core import build_welcomes, render_message


def make_cfg(**kwargs) -> WelcomerConfig:
    defaults = {
        "title": "Test",
        "message": "Hello, {name}!",
        "channels": ["#general"],
        "recipients": [RecipientConfig(name="Alice"), RecipientConfig(name="Bob")],
    }
    defaults.update(kwargs)
    return WelcomerConfig(**defaults)


def test_render_message_basic():
    r = RecipientConfig(name="Alice")
    assert render_message("Hello, {name}!", r) == "Hello, Alice!"


def test_render_message_extra_fields():
    r = RecipientConfig(name="Bob", extra={"role": "admin"})
    assert render_message("Hi {name}, role={role}", r) == "Hi Bob, role=admin"


def test_build_welcomes_channels():
    cfg = make_cfg(channels=["#a", "#b"])
    results = build_welcomes(cfg)
    channels = {r.channel for r in results}
    assert "#a" in channels
    assert "#b" in channels


def test_build_welcomes_dry_run():
    cfg = make_cfg()
    results = build_welcomes(cfg, dry_run=True)
    assert all(r.dry_run for r in results)


def test_build_welcomes_recipient_tags_override():
    cfg = make_cfg(
        channels=["#general"],
        recipients=[
            RecipientConfig(name="Alice", tags=["#vip"]),
        ],
    )
    results = build_welcomes(cfg)
    assert len(results) == 1
    assert results[0].channel == "#vip"


def test_build_welcomes_empty_recipients():
    cfg = make_cfg(recipients=[])
    assert build_welcomes(cfg) == []
