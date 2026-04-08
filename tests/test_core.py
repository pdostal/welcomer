"""Tests for core welcomer logic."""

from datetime import date

from welcomer.config import WelcomerConfig
from welcomer.core import _render, build_welcomes
from welcomer.ical import Recipient


def make_cfg(**kwargs) -> WelcomerConfig:
    defaults = {"subject": "Welcome, {{ name }}!", "body": "Hi {{ name }}."}
    defaults.update(kwargs)
    return WelcomerConfig(**defaults)


def make_recipient(**kwargs) -> Recipient:
    defaults = {"name": "Alice", "email": "alice@example.com"}
    defaults.update(kwargs)
    return Recipient(**defaults)


# ---------------------------------------------------------------------------
# Basic variable rendering
# ---------------------------------------------------------------------------


def test_render_name():
    r = make_recipient()
    assert _render("Hello, {{ name }}!", r) == "Hello, Alice!"


def test_render_email():
    r = make_recipient()
    assert _render("{{ name }} <{{ email }}>", r) == "Alice <alice@example.com>"


def test_render_dates():
    r = make_recipient(start=date(2026, 4, 1), end=date(2026, 4, 8))
    assert _render("{{ start }} to {{ end }}", r) == "2026-04-01 to 2026-04-08"


def test_render_phone():
    r = make_recipient(phone="+420123456789")
    assert _render("Call {{ phone }}", r) == "Call +420123456789"


def test_render_phone_empty_string_when_missing():
    r = make_recipient()  # phone defaults to ""
    assert _render("Call {{ phone }}", r) == "Call "


def test_render_none_dates_produce_empty_strings():
    r = make_recipient(start=None, end=None)
    assert _render("{{ start }}/{{ end }}", r) == "/"


def test_render_summary_from_extra():
    r = make_recipient(extra={"summary": "Onboarding Week"})
    assert _render("{{ summary }}", r) == "Onboarding Week"


def test_render_property_and_provider():
    r = make_recipient(extra={"property": "Horský Apartmán", "provider": "HousePal"})
    assert _render("{{ property }} via {{ provider }}", r) == "Horský Apartmán via HousePal"


def test_render_official_name():
    r = make_recipient(extra={"official_name": "Horský Apartmán s.r.o."})
    assert _render("Legal: {{ official_name }}", r) == "Legal: Horský Apartmán s.r.o."


def test_render_official_name_defaults_to_property():
    """When official_name is not set, it falls back to the property value."""
    r = make_recipient(extra={"property": "Chalupa U Lesa"})
    assert _render("Legal: {{ official_name }}", r) == "Legal: Chalupa U Lesa"


def test_render_official_name_empty_when_no_property_either():
    r = make_recipient()  # no official_name, no property in extra
    assert _render("Legal: {{ official_name }}", r) == "Legal: "


def test_render_adults_and_kids():
    r = make_recipient(adults=2, kids=1)
    assert _render("Guests: {{ adults }} adults, {{ kids }} kids", r) == "Guests: 2 adults, 1 kids"


def test_render_adults_missing_renders_empty():
    r = make_recipient()  # adults=None, kids=None by default
    assert _render("a:{{ adults }} k:{{ kids }}", r) == "a: k:"


# ---------------------------------------------------------------------------
# Jinja2-specific features
# ---------------------------------------------------------------------------


def test_jinja2_if_condition_true():
    r = make_recipient(phone="+123")
    assert _render("{% if phone %}has phone{% endif %}", r) == "has phone"


def test_jinja2_if_condition_false():
    r = make_recipient()  # phone is empty string
    assert _render("{% if phone %}has phone{% endif %}", r) == ""


def test_jinja2_if_else():
    r = make_recipient()
    result = _render("{{ phone if phone else 'N/A' }}", r)
    assert result == "N/A"


def test_jinja2_if_else_phone_present():
    r = make_recipient(phone="+420123456789")
    result = _render("{{ phone if phone else 'N/A' }}", r)
    assert result == "+420123456789"


def test_jinja2_if_adults_block():
    r = make_recipient(adults=2, kids=0)
    result = _render("{% if adults %}{{ adults }} adult(s){% endif %}", r)
    assert result == "2 adult(s)"


def test_jinja2_if_adults_missing():
    r = make_recipient()  # adults=""
    result = _render("{% if adults %}{{ adults }} adult(s){% endif %}", r)
    assert result == ""


def test_jinja2_nested_if():
    r = make_recipient(adults=2, kids=1)
    tmpl = "{% if adults %}{{ adults }} adults{% if kids %}, {{ kids }} kids{% endif %}{% endif %}"
    assert _render(tmpl, r) == "2 adults, 1 kids"


def test_jinja2_filter_upper():
    r = make_recipient()
    assert _render("{{ name | upper }}", r) == "ALICE"


def test_jinja2_filter_default_boolean():
    """default(value, boolean=True) treats empty string as missing."""
    r = make_recipient()
    assert _render("{{ phone | default('no phone', true) }}", r) == "no phone"


def test_jinja2_filter_default_boolean_present():
    r = make_recipient(phone="+123")
    assert _render("{{ phone | default('no phone', true) }}", r) == "+123"


def test_jinja2_or_shorthand():
    r = make_recipient()
    assert _render("{{ phone or 'unknown' }}", r) == "unknown"


def test_jinja2_undefined_variable_renders_empty():
    r = make_recipient()
    # 'nonexistent' is not in context — renders as empty string
    assert _render("{{ nonexistent }}", r) == ""


def test_jinja2_multiline_block():
    r = make_recipient(phone="+123", adults=2)
    tmpl = (
        "Dear {{ name }},\n"
        "{% if phone %}Call: {{ phone }}\n{% endif %}"
        "{% if adults %}Guests: {{ adults }}\n{% endif %}"
    )
    result = _render(tmpl, r)
    assert "Dear Alice," in result
    assert "Call: +123" in result
    assert "Guests: 2" in result


# ---------------------------------------------------------------------------
# build_welcomes
# ---------------------------------------------------------------------------


def test_build_welcomes_subject_and_body():
    cfg = make_cfg(subject="Hi {{ name }}", body="Welcome {{ email }}")
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


def test_build_welcomes_not_dry_run_by_default():
    cfg = make_cfg()
    results = build_welcomes(cfg, [make_recipient()])
    assert results[0].dry_run is False


def test_build_welcomes_result_fields():
    cfg = make_cfg(subject="Hello {{ name }}", body="Welcome {{ email }}")
    r = make_recipient(name="Alice", email="alice@example.com")
    result = build_welcomes(cfg, [r])[0]
    assert result.recipient == "Alice"
    assert result.email == "alice@example.com"
    assert result.subject == "Hello Alice"
    assert result.body == "Welcome alice@example.com"


def test_build_welcomes_jinja2_conditional_in_subject():
    cfg = make_cfg(
        subject="Hi {{ name }}{% if phone %} ({{ phone }}){% endif %}",
        body=".",
    )
    with_phone = build_welcomes(cfg, [make_recipient(phone="+123")])[0]
    without_phone = build_welcomes(cfg, [make_recipient()])[0]
    assert with_phone.subject == "Hi Alice (+123)"
    assert without_phone.subject == "Hi Alice"
