"""Bundled test data for --test-config mode.

All dates are computed relative to today so the data never goes stale.
One reservation (Radka Horáčková at Chalupa U Lesa) is pre-seeded as already
sent, and Horský Apartmán always has an overlap between HousePal and StayBook.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..config import CalendarConfig, MessageConfig, WelcomerConfig
from ..ical import Recipient

# Offsets from today (in days) for each test guest
_KLARA_START = -3  # in-progress: checked in 3 days ago
_KLARA_END = 4
_CLOSED_START = 30
_CLOSED_END = 37
_RADKA_START = 50  # pre-seeded as already sent
_RADKA_END = 59
_ANNA_START = 60
_ANNA_END = 69
_BOOKING_OVERLAP_START = 65  # overlaps with Anna (60–69) at Horský Apartmán
_BOOKING_OVERLAP_END = 74
_TOMAS_START = 10  # same guest at two properties through HousePal → merges to Multi
_TOMAS_END = 17
_TIPSY_1_START = 80
_TIPSY_1_END = 87
_PAVEL_START = 100
_PAVEL_END = 109
_TIPSY_2_START = 120
_TIPSY_2_END = 127
_JIRI_START = 150
_JIRI_END = 159

TEST_CONFIG = WelcomerConfig(
    date_format="%d. %m. %Y",
    messages=[
        MessageConfig(
            name="default",
            subject="Welcome to {{ property }}, {{ name }}!",
            body="""\
Dear {{ name }},

Great news — your stay at **{{ property }}** is locked in! 🎉

You'll be arriving on **{{ start }}** and checking out on **{{ end }}**.
We'll have the place ready, the kettle on, and a moderately
enthusiastic welcome waiting for you.

{% if official_name != property %}{{ official_name }}{% endif %}
Got questions before you arrive? We're reachable by email.
We promise to reply before your check-in date. Probably.

See you soon — try not to lose your keys on the way,

The {{ property }} team
""",
        )
    ],
    advance=14,
)


def get_test_calendars() -> list[tuple[CalendarConfig, list[Recipient]]]:
    """Return test calendars with recipients whose dates are always near-future."""
    t = date.today()
    return [
        (
            CalendarConfig(
                property="Horský Apartmán",
                official_name="Horský Apartmán s.r.o.",
                provider="HousePal",
                url="",
                message="default",
            ),
            [
                Recipient(
                    name="Tomáš Procházka",
                    email="tomas.prochazka@email.cz",
                    phone="+420608901234",
                    start=t + timedelta(days=_TOMAS_START),
                    end=t + timedelta(days=_TOMAS_END),
                ),
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
            CalendarConfig(
                property="Horský Apartmán",
                official_name="Horský Apartmán s.r.o.",
                provider="StayBook",
                url="",
                message="default",
            ),
            [
                Recipient(
                    name="CLOSED - Not available",
                    email=None,
                    start=t + timedelta(days=_CLOSED_START),
                    end=t + timedelta(days=_CLOSED_END),
                ),
                Recipient(
                    name="CLOSED - Not available",
                    email=None,
                    start=t + timedelta(days=_BOOKING_OVERLAP_START),
                    end=t + timedelta(days=_BOOKING_OVERLAP_END),
                ),
            ],
        ),
        (
            CalendarConfig(
                property="Chalupa U Lesa",
                official_name="Chalupa U Lesa - J. Novák",
                provider="HousePal",
                url="",
                message="default",
            ),
            [
                Recipient(
                    name="Klára Novotná",
                    email="klara.novotna@gmail.com",
                    phone="+420607890123",
                    start=t + timedelta(days=_KLARA_START),
                    end=t + timedelta(days=_KLARA_END),
                ),
                Recipient(
                    name="Tomáš Procházka",
                    email="tomas.prochazka@email.cz",
                    phone="+420608901234",
                    start=t + timedelta(days=_TOMAS_START),
                    end=t + timedelta(days=_TOMAS_END),
                ),
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
                    phone="+420 606 789 012",  # spaces stripped on display
                    start=t + timedelta(days=_JIRI_START),
                    end=t + timedelta(days=_JIRI_END),
                ),
            ],
        ),
        (
            CalendarConfig(
                property="Apartmán Sluneční",
                official_name="",
                provider="StayBook",
                url="",
                message="default",
            ),
            [
                Recipient(
                    name="CLOSED - Not available",
                    email=None,
                    start=t + timedelta(days=_TIPSY_1_START),
                    end=t + timedelta(days=_TIPSY_1_END),
                ),
                Recipient(
                    name="CLOSED - Not available",
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
    return f"Chalupa U Lesa|{start}|{end}|Radka Horáčková|radka.horac@post.cz"
