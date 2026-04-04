"""Tests for config loading."""

from unittest.mock import patch

import pytest

from welcomer.config import WelcomerConfig, find_default_config

SAMPLE = {
    "subject": "Hello {name}!",
    "body": "Hi {name}, welcome aboard.",
    "calendars": [
        {"url": "https://example.com/a.ics", "name": "Cal A"},
        {"url": "https://example.com/b.ics"},
    ],
}


def test_from_dict_basic():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert cfg.subject == "Hello {name}!"
    assert cfg.body == "Hi {name}, welcome aboard."
    assert len(cfg.calendars) == 2


def test_calendars_parsed():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert cfg.calendars[0].url == "https://example.com/a.ics"
    assert cfg.calendars[0].name == "Cal A"
    assert cfg.calendars[1].name == ""


def test_defaults():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.subject == "Welcome"
    assert cfg.body == "Hello, {name}!"
    assert cfg.calendars == []


def test_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        'subject = "Loaded"\nbody = "Hey {name}"\n\n'
        '[[calendars]]\nurl = "https://example.com/cal.ics"\nname = "Test Cal"\n',
        encoding="utf-8",
    )
    cfg = WelcomerConfig.from_file(toml)
    assert cfg.subject == "Loaded"
    assert cfg.calendars[0].url == "https://example.com/cal.ics"


def test_raw_preserved():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert cfg.raw == SAMPLE


def test_from_file_missing_raises():
    with pytest.raises(FileNotFoundError):
        WelcomerConfig.from_file("/nonexistent/path/config.toml")


def test_from_file_invalid_toml(tmp_path):
    import tomllib

    bad = tmp_path / "bad.toml"
    bad.write_text("subject = [unclosed", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        WelcomerConfig.from_file(bad)


def test_days_loaded_from_config():
    cfg = WelcomerConfig.from_dict({"days": 14})
    assert cfg.days == 14


def test_days_defaults_to_none():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.days is None


def test_advance_loaded_from_config():
    cfg = WelcomerConfig.from_dict({"advance": 7})
    assert cfg.advance == 7


def test_advance_defaults_to_14():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.advance == 14


def test_find_default_config_local_takes_priority(tmp_path):
    local = tmp_path / "config.toml"
    xdg = tmp_path / "welcomer" / "config.toml"
    local.touch()
    xdg.parent.mkdir()
    xdg.touch()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg),
    ):
        assert find_default_config() == local


def test_find_default_config_falls_back_to_xdg(tmp_path):
    local = tmp_path / "config.toml"
    xdg = tmp_path / "welcomer" / "config.toml"
    xdg.parent.mkdir()
    xdg.touch()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg),
    ):
        assert find_default_config() == xdg


def test_find_default_config_neither_exists(tmp_path):
    local = tmp_path / "config.toml"
    xdg = tmp_path / "welcomer" / "config.toml"
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg),
    ):
        # Returns xdg path even when missing (caller handles the missing file)
        assert find_default_config() == xdg
