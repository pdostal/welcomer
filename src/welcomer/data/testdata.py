"""Bundled test data for --test-config mode.

All dates are computed relative to today so the data never goes stale.
One reservation (Radka Horáčková at The Snoring Goat) is pre-seeded as already
sent, and Biscuit Château always has an overlap between SnoozePal and NapHub.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..config import CalendarConfig, WelcomerConfig
from ..ical import Recipient

# Offsets from today (in days) for each test guest
_CLOSED_START = 30
_CLOSED_END = 37
_RADKA_START = 50  # pre-seeded as already sent
_RADKA_END = 59
_ANNA_START = 60
_ANNA_END = 69
_NAPUB_OVERLAP_START = 65  # overlaps with Anna (60–69) at Biscuit Château
_NAPUB_OVERLAP_END = 74
_TIPSY_1_START = 80
_TIPSY_1_END = 87
_PAVEL_START = 100
_PAVEL_END = 109
_TIPSY_2_START = 120
_TIPSY_2_END = 127
_JIRI_START = 150
_JIRI_END = 159

TEST_CONFIG = WelcomerConfig(
    subject="Welcome to {property}, {name}!",
    date_format="%d. %m. %Y",
    body="""\
Dear {name},

Great news — your stay at **{property}** is locked in! 🎉

You'll be arriving on **{start}** and checking out on **{end}**.
We'll have the place ready, the kettle on, and a moderately
enthusiastic welcome waiting for you.

Got questions before you arrive? We're reachable by email or phone.
We promise to reply before your check-in date. Probably.

See you soon — try not to lose your keys on the way,

The {property} team
""",
    advance=14,
)


def get_test_calendars() -> list[tuple[CalendarConfig, list[Recipient]]]:
    """Return test calendars with recipients whose dates are always near-future."""
    t = date.today()
    return [
        (
            CalendarConfig(name="Biscuit Château", provider="SnoozePal", url=""),
            [
                Recipient(
                    name="Anna Dvořáková",
                    email="anna.dvorakova@seznam.cz",
                    phone="+420603456789",
                    start=t + timedelta(days=_ANNA_START),
                    end=t + timedelta(days=_ANNA_END),
                ),
                Recipient(
                    name="Pavel Kratochvíl",
                    email="pavel.kratochvil@volny.cz",
                    phone="+420604567890",
                    start=t + timedelta(days=_PAVEL_START),
                    end=t + timedelta(days=_PAVEL_END),
                ),
            ],
        ),
        (
            CalendarConfig(name="Biscuit Château", provider="NapHub", url=""),
            [
                Recipient(
                    name="CLOSED - Not available",
                    email=None,
                    start=t + timedelta(days=_CLOSED_START),
                    end=t + timedelta(days=_CLOSED_END),
                ),
                Recipient(
                    name="Reservation",
                    email=None,
                    start=t + timedelta(days=_NAPUB_OVERLAP_START),
                    end=t + timedelta(days=_NAPUB_OVERLAP_END),
                ),
            ],
        ),
        (
            CalendarConfig(name="The Snoring Goat", provider="SnoozePal", url=""),
            [
                Recipient(
                    name="Radka Horáčková",
                    email="radka.horac@post.cz",
                    phone="+420605678901",
                    start=t + timedelta(days=_RADKA_START),
                    end=t + timedelta(days=_RADKA_END),
                ),
                Recipient(
                    name="Jiří Svoboda",
                    email="jiri.svoboda@centrum.cz",
                    phone="+420606789012",
                    start=t + timedelta(days=_JIRI_START),
                    end=t + timedelta(days=_JIRI_END),
                ),
            ],
        ),
        (
            CalendarConfig(name="The Tipsy Gnome", provider="NapHub", url=""),
            [
                Recipient(
                    name="Reservation",
                    email=None,
                    start=t + timedelta(days=_TIPSY_1_START),
                    end=t + timedelta(days=_TIPSY_1_END),
                ),
                Recipient(
                    name="Reservation",
                    email=None,
                    start=t + timedelta(days=_TIPSY_2_START),
                    end=t + timedelta(days=_TIPSY_2_END),
                ),
            ],
        ),
    ]


def get_pre_sent_key() -> str:
    """Return the sent.log key for the pre-seeded entry (Radka Horáčková)."""
    t = date.today()
    start = t + timedelta(days=_RADKA_START)
    end = t + timedelta(days=_RADKA_END)
    return f"The Snoring Goat|{start}|{end}|Radka Horáčková|radka.horac@post.cz"
