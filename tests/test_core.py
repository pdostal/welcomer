"""Tests for core welcomer logic."""

from datetime import date

from welcomer.config import WelcomerConfig
from welcomer.core import _render, build_welcomes
from welcomer.ical import Recipient


def make_cfg(**kwargs) -> WelcomerConfig:
    defaults = {"subject": "Welcome, {name}!", "body": "Hi {name}."}
    defaults.update(kwargs)
    return WelcomerConfig(**defaults)


def make_recipient(**kwargs) -> Recipient:
    defaults = {"name": "Alice", "email": "alice@example.com"}
    defaults.update(kwargs)
    return Recipient(**defaults)


def test_render_name():
    r = make_recipient()
    assert _render("Hello, {name}!", r) == "Hello, Alice!"


def test_render_email():
    r = make_recipient()
    assert _render("{name} <{email}>", r) == "Alice <alice@example.com>"


def test_render_dates():
    r = make_recipient(start=date(2026, 4, 1), end=date(2026, 4, 8))
    assert _render("{start} to {end}", r) == "2026-04-01 to 2026-04-08"


def test_build_welcomes_subject_and_body():
    cfg = make_cfg(subject="Hi {name}", body="Welcome {email}")
    results = build_welcomes(cfg, [make_recipient()])
    assert results[0].subject == "Hi Alice"
    assert results[0].body == "Welcome alice@example.com"


def test_build_welcomes_dry_run():
    cfg = make_cfg()
    results = build_welcomes(cfg, [make_recipient()], dry_run=True)
    assert all(r.dry_run for r in results)


def test_build_welcomes_multiple_recipients():
    cfg = make_cfg()
    recipients = [
        make_recipient(name="Alice", email="a@x.com"),
        make_recipient(name="Bob", email="b@x.com"),
    ]
    results = build_welcomes(cfg, recipients)
    assert {r.recipient for r in results} == {"Alice", "Bob"}


def test_build_welcomes_empty():
    cfg = make_cfg()
    assert build_welcomes(cfg, []) == []
