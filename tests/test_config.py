"""Tests for config loading."""

from welcomer.config import WelcomerConfig

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
