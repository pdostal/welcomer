"""Tests for iCal parsing."""

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from welcomer.ical import (
    _adults_from_description,
    _email_from_description,
    _extract_cn,
    _kids_from_description,
    _parse_email,
    _phone_from_description,
    _to_date,
    fetch_recipients,
    recipients_from_ical,
)

FIXTURES = Path(__file__).parent / "fixtures"

ICAL_WITH_ATTENDEES = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Onboarding
DTSTART;VALUE=DATE:20260401
DTEND;VALUE=DATE:20260408
ATTENDEE;CN="Alice Smith":mailto:alice@example.com
ATTENDEE;CN="Bob Jones":mailto:bob@example.com
END:VEVENT
END:VCALENDAR
"""

ICAL_WITH_ORGANIZER_ONLY = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Solo Event
DTSTART;VALUE=DATE:20260501
DTEND;VALUE=DATE:20260502
ORGANIZER;CN="Carol Davis":mailto:carol@example.com
END:VEVENT
END:VCALENDAR
"""

ICAL_EMPTY = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
END:VCALENDAR
"""

ICAL_ATTENDEE_NO_CN = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:No CN Event
DTSTART;VALUE=DATE:20260401
DTEND;VALUE=DATE:20260408
ATTENDEE:mailto:noname@example.com
END:VEVENT
END:VCALENDAR
"""

ICAL_NO_DTEND = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:No End Event
DTSTART;VALUE=DATE:20260401
ATTENDEE;CN="Eve":mailto:eve@example.com
END:VEVENT
END:VCALENDAR
"""

ICAL_MULTI_EVENT = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Event One
DTSTART;VALUE=DATE:20260401
DTEND;VALUE=DATE:20260402
ATTENDEE;CN="Alice":mailto:alice@example.com
END:VEVENT
BEGIN:VEVENT
SUMMARY:Event Two
DTSTART;VALUE=DATE:20260501
DTEND;VALUE=DATE:20260502
ATTENDEE;CN="Bob":mailto:bob@example.com
END:VEVENT
END:VCALENDAR
"""

ICAL_DATETIME_START = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Datetime Event
DTSTART:20260401T120000Z
DTEND:20260401T130000Z
ATTENDEE;CN="Dave":mailto:dave@example.com
END:VEVENT
END:VCALENDAR
"""


def test_attendees_extracted():
    recipients = recipients_from_ical(ICAL_WITH_ATTENDEES)
    assert len(recipients) == 2
    names = {r.name for r in recipients}
    assert "Alice Smith" in names
    assert "Bob Jones" in names


def test_emails_extracted():
    recipients = recipients_from_ical(ICAL_WITH_ATTENDEES)
    emails = {r.email for r in recipients}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


def test_dates_extracted():
    recipients = recipients_from_ical(ICAL_WITH_ATTENDEES)
    assert all(r.start == date(2026, 4, 1) for r in recipients)
    assert all(r.end == date(2026, 4, 8) for r in recipients)


def test_organizer_fallback():
    recipients = recipients_from_ical(ICAL_WITH_ORGANIZER_ONLY)
    assert len(recipients) == 1
    assert recipients[0].name == "Carol Davis"
    assert recipients[0].email == "carol@example.com"


def test_empty_calendar():
    recipients = recipients_from_ical(ICAL_EMPTY)
    assert recipients == []


def test_attendee_without_cn_uses_email_as_name():
    recipients = recipients_from_ical(ICAL_ATTENDEE_NO_CN)
    assert len(recipients) == 1
    assert recipients[0].email == "noname@example.com"
    assert recipients[0].name == "noname@example.com"


def test_missing_dtend_is_none():
    recipients = recipients_from_ical(ICAL_NO_DTEND)
    assert len(recipients) == 1
    assert recipients[0].start == date(2026, 4, 1)
    assert recipients[0].end is None


def test_multiple_events_produce_separate_recipients():
    recipients = recipients_from_ical(ICAL_MULTI_EVENT)
    assert len(recipients) == 2
    names = {r.name for r in recipients}
    assert names == {"Alice", "Bob"}


def test_multi_event_dates_are_independent():
    recipients = recipients_from_ical(ICAL_MULTI_EVENT)
    by_name = {r.name: r for r in recipients}
    assert by_name["Alice"].start == date(2026, 4, 1)
    assert by_name["Bob"].start == date(2026, 5, 1)


def test_datetime_dtstart_is_converted_to_date():
    recipients = recipients_from_ical(ICAL_DATETIME_START)
    assert len(recipients) == 1
    assert recipients[0].start == date(2026, 4, 1)


def test_summary_stored_in_extra():
    recipients = recipients_from_ical(ICAL_WITH_ATTENDEES)
    assert all(r.extra.get("summary") == "Onboarding" for r in recipients)


# --- _to_date unit tests ---


def test_to_date_none():
    assert _to_date(None) is None


def test_to_date_date():
    d = date(2026, 4, 1)
    assert _to_date(d) == d


def test_to_date_datetime():
    dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    assert _to_date(dt) == date(2026, 4, 1)


def test_to_date_unknown_returns_none():
    assert _to_date("not-a-date") is None


# --- _parse_email unit tests ---


def test_parse_email_strips_mailto():
    assert _parse_email("mailto:foo@example.com") == "foo@example.com"


def test_parse_email_strips_mailto_case_insensitive():
    assert _parse_email("MAILTO:foo@example.com") == "foo@example.com"


def test_parse_email_no_prefix_unchanged():
    assert _parse_email("foo@example.com") == "foo@example.com"


# --- _extract_cn unit tests ---


def test_extract_cn_none():
    assert _extract_cn(None) == ""


def test_extract_cn_with_params():
    prop = SimpleNamespace(params={"CN": "Jane Doe"})
    assert _extract_cn(prop) == "Jane Doe"


def test_extract_cn_missing_cn_key():
    prop = SimpleNamespace(params={})
    assert _extract_cn(prop) == ""


def test_extract_cn_strips_quotes():
    prop = SimpleNamespace(params={"CN": '"Quoted Name"'})
    assert _extract_cn(prop) == "Quoted Name"


# --- fetch_recipients unit tests ---


def test_fetch_recipients_success():
    mock_response = MagicMock()
    mock_response.content = ICAL_WITH_ATTENDEES
    with (
        patch("welcomer.ical.get_cached", return_value=None),
        patch("welcomer.ical.save_cache"),
        patch("httpx.get", return_value=mock_response) as mock_get,
    ):
        result = fetch_recipients("https://example.com/cal.ics")
    mock_get.assert_called_once_with(
        "https://example.com/cal.ics", follow_redirects=True, timeout=15
    )
    mock_response.raise_for_status.assert_called_once()
    assert len(result) == 2


def test_fetch_recipients_raises_on_http_error():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    with (
        patch("welcomer.ical.get_cached", return_value=None),
        patch("httpx.get", return_value=mock_response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        fetch_recipients("https://example.com/cal.ics")


def test_fetch_recipients_raises_on_timeout():
    with (
        patch("welcomer.ical.get_cached", return_value=None),
        patch("httpx.get", side_effect=httpx.TimeoutException("timed out")),
        pytest.raises(httpx.TimeoutException),
    ):
        fetch_recipients("https://example.com/cal.ics")


# --- tests against the real fixture (e-chalupy.cz format) ---


def test_echalupy_fixture_count():
    data = (FIXTURES / "cal.ics").read_bytes()
    recipients = recipients_from_ical(data)
    assert len(recipients) == 2


def test_echalupy_names_from_summary():
    data = (FIXTURES / "cal.ics").read_bytes()
    names = {r.name for r in recipients_from_ical(data)}
    assert "Josef Novák" in names
    assert "Tomáš Jedno" in names


def test_echalupy_emails_from_description():
    data = (FIXTURES / "cal.ics").read_bytes()
    emails = {r.email for r in recipients_from_ical(data)}
    assert "josef@novak.cz" in emails
    assert "tomas.jedno@tiscali.cz" in emails


def test_echalupy_phones_from_description():
    data = (FIXTURES / "cal.ics").read_bytes()
    by_name = {r.name: r for r in recipients_from_ical(data)}
    assert by_name["Josef Novák"].phone == "+420123123123"
    assert by_name["Tomáš Jedno"].phone == "+420773000123"


def test_echalupy_dates():
    data = (FIXTURES / "cal.ics").read_bytes()
    recipients = recipients_from_ical(data)
    by_name = {r.name: r for r in recipients}
    assert by_name["Josef Novák"].start == date(2026, 4, 17)
    assert by_name["Josef Novák"].end == date(2026, 4, 19)
    assert by_name["Tomáš Jedno"].start == date(2026, 6, 11)
    assert by_name["Tomáš Jedno"].end == date(2026, 6, 13)


# --- _email_from_description unit tests ---


def test_email_from_description_extracts_value():
    assert _email_from_description("Email: foo@example.com\n") == "foo@example.com"


def test_email_from_description_empty_field_returns_empty():
    # The problematic case: empty Email followed by Dospělí on the next line.
    # \s* used to gobble the newline and match "Dospělí:" as the email value.
    assert _email_from_description("Email: \nDospělí: 2, děti 0\n") == ""


def test_email_from_description_no_field_returns_empty():
    assert _email_from_description("Telefon: 123456789\n") == ""


# --- _phone_from_description unit tests ---


def test_phone_from_description_empty_field_returns_empty():
    assert _phone_from_description("Telefon: \nEmail: foo@bar.com\n") == ""


# --- _adults_from_description unit tests ---


def test_adults_from_description_parses_count():
    assert _adults_from_description("Dospělí: 2, děti 0\n") == 2


def test_adults_from_description_zero():
    assert _adults_from_description("Dospělí: 0, děti 1\n") == 0


def test_adults_from_description_missing_returns_none():
    assert _adults_from_description("Email: foo@example.com\n") is None


def test_adults_from_description_full_echalupy_block():
    desc = "Telefon: \nEmail: \nDospělí: 3, děti 1\n"
    assert _adults_from_description(desc) == 3


# --- _kids_from_description unit tests ---


def test_kids_from_description_parses_count():
    assert _kids_from_description("Dospělí: 2, děti 1\n") == 1


def test_kids_from_description_zero():
    assert _kids_from_description("Dospělí: 2, děti 0\n") == 0


def test_kids_from_description_missing_returns_none():
    assert _kids_from_description("Email: foo@example.com\n") is None


# --- adults/kids wired through recipients_from_ical ---

ICAL_WITH_ADULTS_KIDS = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
    b"BEGIN:VEVENT\r\n"
    b"SUMMARY:Jan Nov\xc3\xa1k\r\n"
    b"DTSTART;VALUE=DATE:20260601\r\n"
    b"DTEND;VALUE=DATE:20260605\r\n"
    b"DESCRIPTION:Telefon: 123456789\\nEmail: jan@example.com\\n"
    b"Dosp\xc4\x9bl\xc3\xad: 2\\, d\xc4\x9bti 1\\n\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)

ICAL_EMPTY_EMAIL_WITH_ADULTS = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Pavel Noname
DTSTART;VALUE=DATE:20260601
DTEND;VALUE=DATE:20260605
DESCRIPTION:Telefon: \\nEmail: \\nDosp\xc4\x9bl\xc3\xad: 2\\, d\xc4\x9bti 0\\n
END:VEVENT
END:VCALENDAR
"""


def test_adults_and_kids_parsed_from_ical():
    recipients = recipients_from_ical(ICAL_WITH_ADULTS_KIDS)
    assert len(recipients) == 1
    assert recipients[0].adults == 2
    assert recipients[0].kids == 1


def test_empty_email_not_replaced_by_dospe_li():
    """Regression: empty Email field must not be filled with 'Dospělí:'."""
    recipients = recipients_from_ical(ICAL_EMPTY_EMAIL_WITH_ADULTS)
    assert len(recipients) == 1
    assert recipients[0].email == ""
    assert recipients[0].adults == 2
    assert recipients[0].kids == 0
