"""Tests for iCal parsing."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from welcomer.ical import (
    _extract_cn,
    _parse_email,
    _to_date,
    fetch_recipients,
    recipients_from_ical,
)

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
    with patch("httpx.get", return_value=mock_response) as mock_get:
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
    with patch("httpx.get", return_value=mock_response), pytest.raises(httpx.HTTPStatusError):
        fetch_recipients("https://example.com/cal.ics")


def test_fetch_recipients_raises_on_timeout():
    with (
        patch("httpx.get", side_effect=httpx.TimeoutException("timed out")),
        pytest.raises(httpx.TimeoutException),
    ):
        fetch_recipients("https://example.com/cal.ics")
