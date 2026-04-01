"""Tests for iCal parsing."""

from datetime import date

from welcomer.ical import recipients_from_ical

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
