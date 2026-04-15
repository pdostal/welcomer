"""Tests for config loading."""

from unittest.mock import patch

import pytest

from welcomer.config import WelcomerConfig, find_default_config

SAMPLE = {
    "message": [
        {"name": "default", "subject": "Hello {name}!", "body": "Hi {name}, welcome aboard."},
        {"name": "vip", "subject": "Welcome, {name}!", "body": "Great to have you."},
    ],
    "calendar": [
        {"url": "https://example.com/a.ics", "property": "Cal A", "message": "default"},
        {"url": "https://example.com/b.ics", "message": "vip"},
    ],
}


def test_from_dict_basic():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert len(cfg.messages) == 2
    assert len(cfg.calendars) == 2


def test_calendars_parsed():
    cfg = WelcomerConfig.from_dict(SAMPLE)
    assert cfg.calendars[0].url == "https://example.com/a.ics"
    assert cfg.calendars[0].property == "Cal A"
    assert cfg.calendars[0].message == "default"
    assert cfg.calendars[1].property == ""
    assert cfg.calendars[1].message == "vip"


def test_calendar_name_key_backward_compat():
    """Old configs using 'name' instead of 'property' still work."""
    cfg = WelcomerConfig.from_dict(
        {
            "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
            "calendar": [
                {"url": "https://example.com/a.ics", "name": "Old Cal", "message": "default"}
            ],
        }
    )
    assert cfg.calendars[0].property == "Old Cal"


def test_calendar_property_takes_precedence_over_name():
    """When both 'property' and 'name' are present, 'property' wins."""
    cfg = WelcomerConfig.from_dict(
        {
            "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
            "calendar": [
                {
                    "url": "https://x.com/a.ics",
                    "property": "New Name",
                    "name": "Old Name",
                    "message": "default",
                }
            ],
        }
    )
    assert cfg.calendars[0].property == "New Name"


def test_calendar_official_name_loaded():
    cfg = WelcomerConfig.from_dict(
        {
            "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
            "calendar": [
                {
                    "url": "https://x.com/a.ics",
                    "property": "Chalupa",
                    "official_name": "Chalupa s.r.o.",
                    "message": "default",
                }
            ],
        }
    )
    assert cfg.calendars[0].official_name == "Chalupa s.r.o."


def test_calendar_official_name_defaults_to_empty():
    cfg = WelcomerConfig.from_dict(
        {
            "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
            "calendar": [
                {"url": "https://x.com/a.ics", "property": "Chalupa", "message": "default"}
            ],
        }
    )
    assert cfg.calendars[0].official_name == ""


def test_defaults():
    cfg = WelcomerConfig.from_dict({})
    assert cfg.calendars == []
    assert cfg.messages == []


def test_message_name_required():
    with pytest.raises(ValueError, match="message name is required"):
        WelcomerConfig.from_dict({"message": [{"subject": "Hi", "body": "Hi"}]})


def test_message_requires_subject_and_body():
    with pytest.raises(ValueError, match="requires subject and body"):
        WelcomerConfig.from_dict({"message": [{"name": "default", "subject": "Hi"}]})


def test_calendar_message_required():
    with pytest.raises(ValueError, match="calendar message is required"):
        WelcomerConfig.from_dict(
            {
                "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
                "calendar": [{"url": "https://example.com/cal.ics"}],
            }
        )


def test_calendar_message_must_exist():
    with pytest.raises(ValueError, match="unknown message"):
        WelcomerConfig.from_dict(
            {
                "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
                "calendar": [{"url": "https://example.com/cal.ics", "message": "missing"}],
            }
        )


def test_top_level_subject_body_rejected():
    with pytest.raises(ValueError, match="top-level subject/body"):
        WelcomerConfig.from_dict({"subject": "Hi", "body": "Hi"})


def test_legacy_calendars_key_rejected():
    with pytest.raises(ValueError, match=r"\[\[calendars\]\]"):
        WelcomerConfig.from_dict(
            {
                "message": [{"name": "default", "subject": "Hi", "body": "Hi"}],
                "calendars": [{"url": "https://example.com/cal.ics", "message": "default"}],
            }
        )


def test_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[[message]]\nname = "default"\nsubject = "Loaded"\nbody = "Hey {name}"\n\n'
        '[[calendar]]\nurl = "https://example.com/cal.ics"\nproperty = "Test Cal"\n'
        'message = "default"\n',
        encoding="utf-8",
    )
    cfg = WelcomerConfig.from_file(toml)
    assert cfg.messages[0].subject == "Loaded"
    assert cfg.calendars[0].url == "https://example.com/cal.ics"


def test_from_file_name_key(tmp_path):
    """Calendar property still accepts the legacy 'name =' key."""
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[[message]]\nname = "default"\nsubject = "Hi"\nbody = "Hi"\n\n'
        '[[calendar]]\nurl = "https://example.com/cal.ics"\nname = "Legacy Cal"\n'
        'message = "default"\n',
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
