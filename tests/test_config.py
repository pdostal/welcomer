"""Tests for config loading."""

from unittest.mock import patch

import pytest

from welcomer.config import WelcomerConfig, find_default_config

SAMPLE = {
    "subject": "Hello {name}!",
    "body": "Hi {name}, welcome aboard.",
    "calendars": [
        {"url": "https://example.com/a.ics", "property": "Cal A"},
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
    assert cfg.calendars[0].property == "Cal A"
    assert cfg.calendars[1].property == ""


def test_calendars_name_key_backward_compat():
    """Old configs using 'name' instead of 'property' still work."""
    cfg = WelcomerConfig.from_dict(
        {"calendars": [{"url": "https://example.com/a.ics", "name": "Old Cal"}]}
    )
    assert cfg.calendars[0].property == "Old Cal"


def test_calendars_property_takes_precedence_over_name():
    """When both 'property' and 'name' are present, 'property' wins."""
    cfg = WelcomerConfig.from_dict(
        {"calendars": [{"url": "https://x.com/a.ics", "property": "New Name", "name": "Old Name"}]}
    )
    assert cfg.calendars[0].property == "New Name"


def test_calendars_official_name_loaded():
    cfg = WelcomerConfig.from_dict(
        {
            "calendars": [
                {
                    "url": "https://x.com/a.ics",
                    "property": "Chalupa",
                    "official_name": "Chalupa s.r.o.",
                }
            ]
        }
    )
    assert cfg.calendars[0].official_name == "Chalupa s.r.o."


def test_calendars_official_name_defaults_to_empty():
    cfg = WelcomerConfig.from_dict(
        {"calendars": [{"url": "https://x.com/a.ics", "property": "Chalupa"}]}
    )
    assert cfg.calendars[0].official_name == ""


def test_defaults():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.subject == "Welcome"
    assert cfg.body == "Hello, {name}!"
    assert cfg.calendars == []


def test_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        'subject = "Loaded"\nbody = "Hey {name}"\n\n'
        '[[calendars]]\nurl = "https://example.com/cal.ics"\nproperty = "Test Cal"\n',
        encoding="utf-8",
    )
    cfg = WelcomerConfig.from_file(toml)
    assert cfg.subject == "Loaded"
    assert cfg.calendars[0].url == "https://example.com/cal.ics"


def test_from_file_name_key(tmp_path):
    """Old config with 'name =' in [[calendars]] still loads."""
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[[calendars]]\nurl = "https://example.com/cal.ics"\nname = "Legacy Cal"\n',
        encoding="utf-8",
    )
    cfg = WelcomerConfig.from_file(toml)
    assert cfg.calendars[0].property == "Legacy Cal"


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


def test_send_without_email_defaults_false():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.send_without_email is False


def test_send_without_email_loaded():
    cfg = WelcomerConfig.from_dict({"send_without_email": True})
    assert cfg.send_without_email is True


def test_smtp_from_name_loaded():
    cfg = WelcomerConfig.from_dict(
        {"smtp": {"host": "smtp.example.com", "from": "info@x.com", "from_name": "My Property"}}
    )
    assert cfg.smtp is not None
    assert cfg.smtp.from_name == "My Property"


def test_smtp_from_name_defaults_empty():
    cfg = WelcomerConfig.from_dict({"smtp": {"host": "smtp.example.com", "from": "info@x.com"}})
    assert cfg.smtp is not None
    assert cfg.smtp.from_name == ""


def test_smtp_cc_loaded_as_list():
    cfg = WelcomerConfig.from_dict(
        {"smtp": {"host": "h", "from": "f@x.com", "cc": ["a@x.com", "b@x.com"]}}
    )
    assert cfg.smtp is not None
    assert cfg.smtp.cc == ["a@x.com", "b@x.com"]


def test_smtp_cc_loaded_as_string():
    """A single string cc value is coerced to a list."""
    cfg = WelcomerConfig.from_dict(
        {"smtp": {"host": "h", "from": "f@x.com", "cc": "manager@x.com"}}
    )
    assert cfg.smtp is not None
    assert cfg.smtp.cc == ["manager@x.com"]


def test_smtp_cc_defaults_empty():
    cfg = WelcomerConfig.from_dict({"smtp": {"host": "h", "from": "f@x.com"}})
    assert cfg.smtp is not None
    assert cfg.smtp.cc == []


def test_smtp_bcc_loaded_as_list():
    cfg = WelcomerConfig.from_dict(
        {"smtp": {"host": "h", "from": "f@x.com", "bcc": ["audit@x.com"]}}
    )
    assert cfg.smtp is not None
    assert cfg.smtp.bcc == ["audit@x.com"]


def test_smtp_bcc_loaded_as_string():
    cfg = WelcomerConfig.from_dict({"smtp": {"host": "h", "from": "f@x.com", "bcc": "audit@x.com"}})
    assert cfg.smtp is not None
    assert cfg.smtp.bcc == ["audit@x.com"]


def test_smtp_bcc_defaults_empty():
    cfg = WelcomerConfig.from_dict({"smtp": {"host": "h", "from": "f@x.com"}})
    assert cfg.smtp is not None
    assert cfg.smtp.bcc == []


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
