"""iCal fetching and recipient extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from icalendar import Calendar, Event

from .cache import get_cached, save_cache

# Pre-compiled regexes for e-chalupy.cz Description field parsing.
_RE_EMAIL = re.compile(r"Email:[ \t]*([^\s\\,;\n]+)", re.IGNORECASE)
_RE_PHONE = re.compile(r"Telefon:[ \t]*([^\s\\,;\n]+)", re.IGNORECASE)
_RE_ADULTS = re.compile(r"Dosp[eě]l[ií]:[ \t]*(\d+)", re.IGNORECASE)
_RE_KIDS = re.compile(r"d[eě]ti[ \t]+(\d+)", re.IGNORECASE)


@dataclass
class Recipient:
    name: str
    email: str
    start: date | None = None
    end: date | None = None
    phone: str = ""
    adults: int | None = None
    kids: int | None = None
    extra: dict = field(default_factory=dict)


def _to_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def _parse_email(value: str) -> str:
    """Strip mailto: prefix if present."""
    return re.sub(r"^mailto:", "", str(value), flags=re.IGNORECASE)


def _extract_cn(prop) -> str:
    if prop is None:
        return ""
    params = getattr(prop, "params", {})
    return str(params.get("CN", "")).strip('"')


def _email_from_description(description: str) -> str:
    """Extract email address from a Description field containing 'Email: ...'."""
    m = _RE_EMAIL.search(description)
    return m.group(1) if m else ""


def _phone_from_description(description: str) -> str:
    """Extract phone number from a Description field containing 'Telefon: ...'."""
    m = _RE_PHONE.search(description)
    return m.group(1) if m else ""


def _adults_from_description(description: str) -> int | None:
    """Extract adult guest count from 'Dospělí: N' in a Description field."""
    m = _RE_ADULTS.search(description)
    return int(m.group(1)) if m else None


def _kids_from_description(description: str) -> int | None:
    """Extract child guest count from 'děti N' in a Description field."""
    m = _RE_KIDS.search(description)
    return int(m.group(1)) if m else None


def recipients_from_ical(data: bytes) -> list[Recipient]:
    """Parse iCal bytes and return a Recipient per attendee per event."""
    cal = Calendar.from_ical(data)
    results: list[Recipient] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        event: Event = component
        start = _to_date(event.get("DTSTART").dt if event.get("DTSTART") else None)
        end = _to_date(event.get("DTEND").dt if event.get("DTEND") else None)
        summary = str(event.get("SUMMARY", ""))

        description = str(event.get("DESCRIPTION", ""))
        phone = _phone_from_description(description)
        adults = _adults_from_description(description)
        kids = _kids_from_description(description)

        attendees = event.get("ATTENDEE")
        if attendees is None:
            attendees = []
        elif not isinstance(attendees, list):
            attendees = [attendees]

        for att in attendees:
            email = _parse_email(att)
            name = _extract_cn(att) or email
            results.append(
                Recipient(
                    name=name,
                    email=email,
                    start=start,
                    end=end,
                    phone=phone,
                    adults=adults,
                    kids=kids,
                    extra={"summary": summary},
                )
            )

        # Fall back to ORGANIZER if no attendees
        if not attendees:
            org = event.get("ORGANIZER")
            if org:
                email = _parse_email(org)
                name = _extract_cn(org) or email
                results.append(
                    Recipient(
                        name=name,
                        email=email,
                        start=start,
                        end=end,
                        phone=phone,
                        adults=adults,
                        kids=kids,
                        extra={"summary": summary},
                    )
                )
            else:
                # Last resort: name from SUMMARY, email from Description
                email = _email_from_description(description)
                if summary or email:
                    results.append(
                        Recipient(
                            name=summary,
                            email=email,
                            start=start,
                            end=end,
                            phone=phone,
                            adults=adults,
                            kids=kids,
                            extra={"summary": summary},
                        )
                    )

    return results


def fetch_recipients(url: str, force_refresh: bool = False) -> list[Recipient]:
    """Fetch an iCal URL and return extracted recipients.

    Results are cached on disk for 5 hours (``~/.config/welcomer/cache/``).
    Pass ``force_refresh=True`` to bypass the cache and always fetch from the
    network, overwriting the existing cached entry.
    """
    if not force_refresh:
        cached = get_cached(url)
        if cached is not None:
            return recipients_from_ical(cached)

    response = httpx.get(url, follow_redirects=True, timeout=15)
    response.raise_for_status()
    save_cache(url, response.content)
    return recipients_from_ical(response.content)
