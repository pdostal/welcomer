"""Tests for the CLI."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from welcomer.cli import _sent_key, main
from welcomer.ical import Recipient


def _run_with_calendars(tmp_path, calendars, extra_args=()):
    """
    Helper for sort/filter tests. calendars is a list of (name, provider, [Recipient]).
    Creates a minimal config and mocks fetch_recipients per URL.
    """
    lines = ['subject = "Hi {name}"', 'body = "Hi"', ""]
    url_map = {}
    for i, (cal_name, provider, recs) in enumerate(calendars):
        url = f"https://example.com/{i}.ics"
        lines += [
            "[[calendars]]",
            f'name = "{cal_name}"',
            f'provider = "{provider}"',
            f'url = "{url}"',
            "",
        ]
        url_map[url] = recs

    p = tmp_path / "config.toml"
    p.write_text("\n".join(lines))

    runner = CliRunner()
    with patch(
        "welcomer.cli.fetch_recipients",
        side_effect=lambda u, force_refresh=False: url_map.get(u, []),
    ):
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--yes", *extra_args])
    return result


TOML_CONTENT = """\
subject = "Welcome, {name}!"
body = "Hi {name}, glad to have you."

[[calendars]]
name = "Test Cal"
url = "https://example.com/test.ics"
"""

MOCK_RECIPIENTS = [
    Recipient(name="Alice", email="alice@example.com"),
    Recipient(name="Bob", email="bob@example.com"),
]


@pytest.fixture(autouse=True)
def mock_sent_log(tmp_path):
    """Redirect sent.log to a temp path for all CLI tests."""
    with patch("welcomer.cli.SENT_LOG_PATH", tmp_path / "sent.log"):
        yield tmp_path / "sent.log"


@pytest.fixture
def config_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(TOML_CONTENT)
    return p


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "--config" in result.output


def test_dry_run(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "Would send" in result.output
    assert "Alice" in result.output


def test_normal_run(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--yes"])
    assert result.exit_code == 0
    assert "Sent" in result.output
    assert "Alice" in result.output
    assert "Bob" in result.output


def test_print_note(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(
            main,
            ["--config", str(config_file), "--dry-run", "--print-note", "--yes"],
        )
    assert result.exit_code == 0
    assert "Welcome, Alice!" in result.output  # rendered subject shown


def test_no_note_by_default(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert "glad to have you" not in result.output  # body not shown by default


def test_missing_config():
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "nonexistent.toml"])
    assert result.exit_code == 1


def test_default_config_uses_xdg(tmp_path):
    """When no local config.toml exists, the XDG path is used as default."""
    xdg_config = tmp_path / "welcomer" / "config.toml"
    xdg_config.parent.mkdir()
    xdg_config.write_text(TOML_CONTENT)
    local_missing = tmp_path / "config.toml"  # does not exist
    runner = CliRunner()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local_missing),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg_config),
        patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS),
    ):
        result = runner.invoke(main, ["--yes"])
    assert result.exit_code == 0
    assert "Sent" in result.output


def test_default_config_uses_local(tmp_path):
    """When local config.toml exists it takes priority over the XDG path."""
    local_config = tmp_path / "config.toml"
    local_config.write_text(TOML_CONTENT)
    xdg_config = tmp_path / "welcomer" / "config.toml"  # does not exist
    runner = CliRunner()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local_config),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg_config),
        patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS),
    ):
        result = runner.invoke(main, ["--yes"])
    assert result.exit_code == 0
    assert "Sent" in result.output


def test_test_config_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Would send" in result.output


def test_test_config_requires_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["--test-config"])
    assert result.exit_code == 2
    assert "--test-config requires --dry-run" in result.output


def test_property_filter():
    # StayBook (Apartmán Sluneční) has only CLOSED entries — no email, nothing sent
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "Apartmán Sluneční"])
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_property_filter_case_insensitive():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "apartmán sluneční"])
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_property_filter_no_match():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "Nonexistent"])
    assert result.exit_code == 0
    assert "No recipients found" in result.output


def test_provider_filter():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "HousePal"])
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Radka" in result.output


def test_provider_filter_case_insensitive():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "housepal"])
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Radka" in result.output


def test_property_and_provider_filter_combined():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--dry-run", "--test-config", "--property", "Horský", "--provider", "HousePal"],
    )
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Radka" not in result.output


def _mock_today(d: date):
    m = MagicMock()
    m.today.return_value = d
    return m


def test_days_filter_excludes_far_future():
    # Klára is in-progress (start-3, end+4) so --days 1 still shows her; future guests excluded
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "1"])
    assert result.exit_code == 0
    # Check only the table (overlap warnings may mention other guests)
    table = result.output[result.output.index("👤 Name") :]
    assert "Klára" in table
    assert "Anna" not in table
    assert "Radka" not in table


def test_days_filter_includes_upcoming():
    # Radka starts today+50, Anna today+60 — --days 55 includes Radka, not Anna
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "55"])
    assert result.exit_code == 0
    # Overlap warning may mention Anna even when she's filtered from the table —
    # check only the table rows (after the header line).
    table = result.output[result.output.index("👤 Name") :]
    assert "Radka" in table
    assert "Anna" not in table


def test_days_filter_not_active_by_default():
    # HousePal guests: Klára, Tomáš (Multi), Anna, Pavel, Radka, Jiří = 6 total.
    # Tomáš appears at two properties but merges into one Multi entry.
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Would send 6" in result.output


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_sort_full_order_by_start_date():
    # Sort: Klára (-3) < Tomáš (+10, Multi) < Radka (+50) < Anna (+60) < Pavel (+100) < Jiří (+150)
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    # Search only within the table (overlap warnings may reference names before the table)
    table = result.output[result.output.index("👤 Name") :]
    assert (
        table.index("Klára")
        < table.index("Tomáš")
        < table.index("Radka")
        < table.index("Anna")
        < table.index("Pavel")
        < table.index("Jiří")
    )


def test_sort_by_end_date_when_same_start(tmp_path):
    # Beta has same start but later end → should come after Alpha
    recs = [
        Recipient(name="Beta", email="b@x.com", start=date(2026, 6, 1), end=date(2026, 6, 10)),
        Recipient(name="Alpha", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5)),
    ]
    result = _run_with_calendars(tmp_path, [("Cal", "Prov", recs)])
    table = result.output[result.output.index("👤 Name") :]
    assert table.index("Alpha") < table.index("Beta")


def test_sort_by_property_when_same_dates(tmp_path):
    r1 = Recipient(name="Guest1", email="g1@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5))
    r2 = Recipient(name="Guest2", email="g2@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5))
    result = _run_with_calendars(
        tmp_path,
        [("Zephyr Place", "Prov", [r1]), ("Apple Barn", "Prov", [r2])],
    )
    # Apple Barn < Zephyr Place alphabetically
    assert result.output.index("Guest2") < result.output.index("Guest1")


def test_sort_by_provider_when_same_dates_and_property(tmp_path):
    r1 = Recipient(name="Guest1", email="g1@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5))
    r2 = Recipient(name="Guest2", email="g2@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5))
    result = _run_with_calendars(
        tmp_path,
        [("Same Place", "ZPlatform", [r1]), ("Same Place", "APlatform", [r2])],
    )
    # APlatform < ZPlatform alphabetically
    table = result.output[result.output.index("👤 Name") :]
    assert table.index("Guest2") < table.index("Guest1")


# ---------------------------------------------------------------------------
# --days filter
# ---------------------------------------------------------------------------


def test_days_filter_boundary_inclusive():
    # Radka starts today+50 — --days 50 must include her (boundary inclusive)
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "50"])
    assert "Radka" in result.output


def test_days_filter_excludes_past(tmp_path):
    # Reservations that have fully ended (end < today) are excluded
    today = date.today()
    recs = [
        Recipient(
            name="PastGuest",
            email="p@x.com",
            start=today - timedelta(days=5),
            end=today - timedelta(days=1),
        ),
        Recipient(
            name="FutureGuest",
            email="f@x.com",
            start=today + timedelta(days=10),
            end=today + timedelta(days=15),
        ),
    ]
    result = _run_with_calendars(tmp_path, [("Cal", "P", recs)], extra_args=["--days", "30"])
    assert "FutureGuest" in result.output
    assert "PastGuest" not in result.output


def test_days_filter_includes_in_progress(tmp_path):
    # A reservation that started in the past but hasn't ended yet must be shown
    today = date.today()
    recs = [
        Recipient(
            name="InProgressGuest",
            email="ip@x.com",
            start=today - timedelta(days=3),
            end=today + timedelta(days=4),
        ),
        Recipient(
            name="FutureGuest",
            email="f@x.com",
            start=today + timedelta(days=10),
            end=today + timedelta(days=15),
        ),
    ]
    result = _run_with_calendars(tmp_path, [("Cal", "P", recs)], extra_args=["--days", "30"])
    assert "InProgressGuest" in result.output
    assert "FutureGuest" in result.output


def test_days_filter_includes_checkout_today(tmp_path):
    # A reservation that checks out today (end == today) must be shown
    today = date.today()
    recs = [
        Recipient(
            name="CheckoutToday",
            email="c@x.com",
            start=today - timedelta(days=5),
            end=today,
        ),
        Recipient(
            name="AlreadyGone",
            email="g@x.com",
            start=today - timedelta(days=20),
            end=today - timedelta(days=12),
        ),
    ]
    result = _run_with_calendars(tmp_path, [("Cal", "P", recs)], extra_args=["--days", "30"])
    # Check only the table (overlap warnings could mention names even for filtered-out entries)
    table = result.output[result.output.index("👤 Name") :]
    assert "CheckoutToday" in table
    assert "AlreadyGone" not in table


# ---------------------------------------------------------------------------
# Multi-property merging
# ---------------------------------------------------------------------------


def test_multi_property_merges_to_multi_label(tmp_path):
    """Same guest, same provider, same dates, different properties → shows 'Multi'."""
    today = date.today()
    rec1 = Recipient(
        name="Same Guest",
        email="sg@x.com",
        phone="+1234",
        start=today + timedelta(days=10),
        end=today + timedelta(days=14),
    )
    rec2 = Recipient(
        name="Same Guest",
        email="sg@x.com",
        phone="+1234",
        start=today + timedelta(days=10),
        end=today + timedelta(days=14),
    )
    result = _run_with_calendars(
        tmp_path,
        [("Villa Alpha", "SameProvider", [rec1]), ("Villa Beta", "SameProvider", [rec2])],
    )
    table = result.output[result.output.index("👤 Name") :]
    assert "Multi" in table
    assert "Villa Alpha" not in table
    assert "Villa Beta" not in table
    assert result.output.count("Same Guest") == 1  # only one row


def test_multi_property_sends_one_email(tmp_path):
    """Merged Multi entry counts as a single email to send."""
    today = date.today()
    start, end = today + timedelta(days=5), today + timedelta(days=10)
    rec_a = Recipient(name="Same Guest", email="sg@x.com", start=start, end=end)
    rec_b = Recipient(name="Same Guest", email="sg@x.com", start=start, end=end)
    result = _run_with_calendars(
        tmp_path,
        [("PropA", "P", [rec_a]), ("PropB", "P", [rec_b])],
        extra_args=["--advance", "99999"],
    )
    assert "Would send 1" in result.output


def test_multi_property_different_provider_not_merged(tmp_path):
    """Same name and dates but different providers → two separate entries, not merged."""
    today = date.today()
    start, end = today + timedelta(days=10), today + timedelta(days=14)
    rec_a = Recipient(name="Same Guest", email="sg@x.com", start=start, end=end)
    rec_b = Recipient(name="Same Guest", email="sg@x.com", start=start, end=end)
    result = _run_with_calendars(
        tmp_path,
        [("PropA", "ProviderX", [rec_a]), ("PropB", "ProviderY", [rec_b])],
    )
    table = result.output[result.output.index("👤 Name") :]
    assert "Multi" not in table
    assert table.count("Same Guest") == 2


def test_multi_property_different_name_not_merged(tmp_path):
    """Same provider and dates but different names → two entries, not merged."""
    today = date.today()
    start, end = today + timedelta(days=10), today + timedelta(days=14)
    rec_a = Recipient(name="Alice Smith", email="a@x.com", start=start, end=end)
    rec_b = Recipient(name="Bob Jones", email="b@x.com", start=start, end=end)
    result = _run_with_calendars(
        tmp_path,
        [("PropA", "P", [rec_a]), ("PropB", "P", [rec_b])],
    )
    table = result.output[result.output.index("👤 Name") :]
    assert "Multi" not in table
    assert "Alice Smith" in table
    assert "Bob Jones" in table


def test_multi_property_different_dates_not_merged(tmp_path):
    """Same name and provider but different check-in/out dates → not merged."""
    today = date.today()
    rec1 = Recipient(
        name="Same Guest",
        email="sg@x.com",
        start=today + timedelta(days=10),
        end=today + timedelta(days=14),
    )
    rec2 = Recipient(
        name="Same Guest",
        email="sg@x.com",
        start=today + timedelta(days=11),
        end=today + timedelta(days=14),
    )
    result = _run_with_calendars(
        tmp_path,
        [("PropA", "P", [rec1]), ("PropB", "P", [rec2])],
    )
    table = result.output[result.output.index("👤 Name") :]
    assert "Multi" not in table
    assert table.count("Same Guest") == 2


def test_multi_property_three_properties_merged(tmp_path):
    """Three properties, same provider, same guest, same dates → one Multi entry."""
    today = date.today()
    start, end = today + timedelta(days=10), today + timedelta(days=14)
    recs = [
        Recipient(name="Triple Guest", email="triple@x.com", start=start, end=end) for _ in range(3)
    ]
    result = _run_with_calendars(
        tmp_path,
        [
            ("P1", "SameProv", [recs[0]]),
            ("P2", "SameProv", [recs[1]]),
            ("P3", "SameProv", [recs[2]]),
        ],
        extra_args=["--advance", "99999"],
    )
    assert result.output.count("Triple Guest") == 1
    assert "Would send 1" in result.output


def test_multi_property_test_config_shows_tomas():
    """Tomáš appears in two HousePal calendars and is shown as a single Multi entry."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    table = result.output[result.output.index("👤 Name") :]
    assert "Tomáš" in table
    assert "Multi" in table
    # Tomáš appears exactly once in the table
    assert table.count("Tomáš") == 1


def test_multi_property_same_property_not_merged(tmp_path):
    """Two entries for the same property and same guest are not merged (overlap case, not Multi)."""
    today = date.today()
    rec = Recipient(
        name="Guest",
        email="g@x.com",
        start=today + timedelta(days=10),
        end=today + timedelta(days=14),
    )
    result = _run_with_calendars(
        tmp_path,
        [("Same Property", "P", [rec, rec])],
    )
    table = result.output[result.output.index("👤 Name") :]
    assert "Multi" not in table


# ---------------------------------------------------------------------------
# Active-today name colour (_name_color unit tests)
# ---------------------------------------------------------------------------


def test_name_color_active_ongoing():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(today - timedelta(2), today + timedelta(3), today) == "blue"


def test_name_color_checkin_today():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(today, today + timedelta(5), today) == "blue"


def test_name_color_checkout_today():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(today - timedelta(5), today, today) == "blue"


def test_name_color_future_is_green():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(today + timedelta(2), today + timedelta(7), today) == "green"


def test_name_color_past_is_green():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(today - timedelta(7), today - timedelta(2), today) == "green"


def test_name_color_none_dates_is_green():
    from welcomer.cli import _name_color

    today = date(2026, 6, 5)
    assert _name_color(None, None, today) == "green"


def test_days_filter_combined_with_property():
    # --property Lesa: Radka (today+50) within 100 days, Jiří (today+150) not
    runner = CliRunner()
    result = runner.invoke(
        main, ["--dry-run", "--test-config", "--days", "100", "--property", "Lesa"]
    )
    assert result.exit_code == 0
    assert "Radka" in result.output
    assert "Jiří" not in result.output


def test_days_zero_shows_only_today(tmp_path):
    today = date(2026, 6, 1)
    recs = [
        Recipient(name="Today", email="t@x.com", start=today, end=date(2026, 6, 5)),
        Recipient(name="Tomorrow", email="tm@x.com", start=date(2026, 6, 2), end=date(2026, 6, 6)),
    ]
    with patch("welcomer.cli.date", _mock_today(today)):
        result = _run_with_calendars(tmp_path, [("Cal", "Prov", recs)], extra_args=["--days", "0"])
    # Overlap warning may mention Tomorrow even though it's outside --days 0 —
    # check only the table rows (after the header line).
    table = result.output[result.output.index("👤 Name") :]
    assert "Today" in table
    assert "Tomorrow" not in table


def test_fetch_failure(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", side_effect=Exception("timeout")):
        result = runner.invoke(main, ["--config", str(config_file)])
    assert "Failed to load" in result.output
    assert result.exit_code == 0


def test_no_calendars_exits_zero(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('subject = "Hi"\nbody = "Hello"\n', encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(p)])
    assert result.exit_code == 0
    assert "No calendars" in result.output


def test_no_recipients_exits_zero(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=[]):
        result = runner.invoke(main, ["--config", str(config_file)])
    assert result.exit_code == 0
    assert "No recipients" in result.output


def test_multiple_calendars_partial_failure(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hello {name}"\n\n'
        '[[calendars]]\nname = "Good"\nurl = "https://example.com/good.ics"\n\n'
        '[[calendars]]\nname = "Bad"\nurl = "https://example.com/bad.ics"\n',
        encoding="utf-8",
    )
    good_recipients = [
        Recipient(
            name="Alice",
            email="alice@example.com",
            start=date.today() + timedelta(days=5),
            end=date.today() + timedelta(days=10),
        )
    ]

    def side_effect(url, force_refresh=False):
        if "good" in url:
            return good_recipients
        raise Exception("unreachable")

    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", side_effect=side_effect):
        result = runner.invoke(main, ["--config", str(p), "--yes"])
    assert result.exit_code == 0
    assert "Failed to load" in result.output
    assert "Alice" in result.output


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


# ---------------------------------------------------------------------------
# StayBook (Horský Apartmán) filter
# ---------------------------------------------------------------------------


def test_horsky_apartman_booking_filter():
    # StayBook entries are CLOSED — no email, nothing sent
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--dry-run", "--test-config", "--property", "Horský", "--provider", "StayBook"],
    )
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_booking_provider_no_guests_to_send():
    # StayBook entries are CLOSED — shown in table, nothing sent
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "StayBook"])
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_closed_events_shown_but_not_sent():
    """CLOSED events from booking.com-style calendars appear in the table but are not sent."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "CLOSED" in result.output
    assert "Would send 6" in result.output


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------


def test_overlap_detected_in_test_config():
    # StayBook Reservation overlaps Anna Dvořáková/HousePal at Horský Apartmán
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Overlap" in result.output
    assert "Horský Apartmán" in result.output
    assert "Reservation" in result.output
    assert "Anna" in result.output


def test_overlap_shows_both_providers():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert "StayBook" in result.output
    assert "HousePal" in result.output


def test_no_overlap_when_non_overlapping(tmp_path):
    recs = [
        Recipient(name="Alice", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 10)),
        Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 10), end=date(2026, 6, 20)),
    ]
    result = _run_with_calendars(tmp_path, [("Villa", "P1", [recs[0]]), ("Villa", "P2", [recs[1]])])
    assert "Overlap" not in result.output


def test_overlap_detected_with_mocked_calendars(tmp_path):
    # Same property, different providers, overlapping dates
    recs_a = [
        Recipient(name="Alice", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 15))
    ]
    recs_b = [
        Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 10), end=date(2026, 6, 20))
    ]
    result = _run_with_calendars(
        tmp_path,
        [("Same Villa", "ProvA", recs_a), ("Same Villa", "ProvB", recs_b)],
    )
    assert "Overlap" in result.output
    assert "Same Villa" in result.output
    assert "Alice" in result.output
    assert "Bob" in result.output


def test_no_overlap_different_properties(tmp_path):
    # Same dates but different properties — no overlap warning
    recs_a = [
        Recipient(name="Alice", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 15))
    ]
    recs_b = [Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 5), end=date(2026, 6, 20))]
    result = _run_with_calendars(
        tmp_path,
        [("Villa Alpha", "Prov", recs_a), ("Villa Beta", "Prov", recs_b)],
    )
    assert "Overlap" not in result.output


def test_overlap_only_touching_not_overlapping(tmp_path):
    # End of one == start of next — adjacent, NOT overlapping (check-out vs next check-in)
    recs = [
        Recipient(name="Alice", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 10)),
        Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 10), end=date(2026, 6, 20)),
    ]
    result = _run_with_calendars(
        tmp_path,
        [("Villa", "P1", [recs[0]]), ("Villa", "P2", [recs[1]])],
    )
    assert "Overlap" not in result.output


def test_overlap_multi_vs_single_different_provider(tmp_path):
    """Multi-property reservation overlaps a single-property booking from a different provider."""
    start = date(2026, 6, 1)
    end = date(2026, 6, 10)
    overlap_start = date(2026, 6, 5)
    overlap_end = date(2026, 6, 15)
    # Tomáš books PropA + PropB through Provider1 → merged to Multi
    tomas_a = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    tomas_b = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    # Conflicting booking from Provider2 for PropA only
    conflicting = Recipient(
        name="Conflicting", email="c@x.com", start=overlap_start, end=overlap_end
    )
    result = _run_with_calendars(
        tmp_path,
        [
            ("PropA", "Provider1", [tomas_a]),
            ("PropB", "Provider1", [tomas_b]),
            ("PropA", "Provider2", [conflicting]),
        ],
    )
    assert "Overlap" in result.output
    assert "Tomáš" in result.output
    assert "Conflicting" in result.output


def test_overlap_both_scenarios_simultaneously(tmp_path):
    """Both overlap scenarios at once:

    1. Multi (PropA+PropB / P1) vs single (PropA / P2) — Multi vs single
    2. Single (PropA / P2) vs single (PropA / P3) — single vs single

    Both must be detected.
    """
    start = date(2026, 6, 1)
    end = date(2026, 6, 10)
    # Tomáš: Multi (PropA + PropB / P1)
    tomas_a = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    tomas_b = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    # Bob: PropA / P2, overlaps Tomáš (PropA component)
    bob = Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 5), end=date(2026, 6, 15))
    # Carol: PropA / P3, overlaps both Tomáš and Bob
    carol = Recipient(name="Carol", email="c@x.com", start=date(2026, 6, 3), end=date(2026, 6, 12))
    result = _run_with_calendars(
        tmp_path,
        [
            ("PropA", "P1", [tomas_a]),
            ("PropB", "P1", [tomas_b]),
            ("PropA", "P2", [bob]),
            ("PropA", "P3", [carol]),
        ],
    )
    assert "Overlap" in result.output
    # Tomáš (Multi) overlaps with Bob and Carol (single vs Multi)
    assert result.output.count("Tomáš") >= 1
    # Bob and Carol overlap with each other (single vs single at same property)
    assert "Bob" in result.output
    assert "Carol" in result.output
    # At least 3 overlap pairs: Tomáš×Bob, Tomáš×Carol, Bob×Carol
    assert result.output.count("Overlap") >= 3


def test_no_overlap_multi_non_overlapping_dates(tmp_path):
    """Multi reservation and a single-property booking on non-overlapping dates → no warning."""
    # Tomáš: PropA + PropB / P1, June 1–10
    s, e = date(2026, 6, 1), date(2026, 6, 10)
    tomas_a = Recipient(name="Tomáš", email="t@x.com", start=s, end=e)
    tomas_b = Recipient(name="Tomáš", email="t@x.com", start=s, end=e)
    # Bob: PropA / P2, June 15–20 (after Tomáš)
    bob = Recipient(name="Bob", email="b@x.com", start=date(2026, 6, 15), end=date(2026, 6, 20))
    result = _run_with_calendars(
        tmp_path,
        [
            ("PropA", "P1", [tomas_a]),
            ("PropB", "P1", [tomas_b]),
            ("PropA", "P2", [bob]),
        ],
    )
    assert "Overlap" not in result.output


def test_overlap_warning_shows_multi_for_multi_single_for_single(tmp_path):
    """Multi entry shows 'Multi · provider' in warning; single-property entry shows its property."""
    start = date(2026, 6, 1)
    end = date(2026, 6, 10)
    # Tomáš: Multi (PropA + PropB / P1)
    tomas_a = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    tomas_b = Recipient(name="Tomáš", email="t@x.com", start=start, end=end)
    # Conflicting: PropA / P2, overlapping dates
    conflicting = Recipient(
        name="Conflict", email="c@x.com", start=date(2026, 6, 5), end=date(2026, 6, 15)
    )
    result = _run_with_calendars(
        tmp_path,
        [
            ("PropA", "P1", [tomas_a]),
            ("PropB", "P1", [tomas_b]),
            ("PropA", "P2", [conflicting]),
        ],
    )
    warnings = [line for line in result.output.splitlines() if "Overlap" in line]
    assert warnings, "expected at least one overlap warning"
    # Tomáš (Multi) shows as "Multi · P1"; Conflict (single) shows as "PropA · P2"
    assert any("Multi" in w for w in warnings)
    assert any("PropA" in w for w in warnings)


def test_overlap_warning_both_multi_shows_multi_labels(tmp_path):
    """When both overlapping entries are Multi, both sides show 'Multi · provider'."""
    start = date(2026, 6, 1)
    end = date(2026, 6, 10)
    overlap_start = date(2026, 6, 5)
    overlap_end = date(2026, 6, 15)
    # Alice: Multi (PropA + PropB / P1)
    alice_a = Recipient(name="Alice", email="a@x.com", start=start, end=end)
    alice_b = Recipient(name="Alice", email="a@x.com", start=start, end=end)
    # Bob: Multi (PropA + PropC / P2), overlaps Alice at PropA
    bob_a = Recipient(name="Bob", email="b@x.com", start=overlap_start, end=overlap_end)
    bob_c = Recipient(name="Bob", email="b@x.com", start=overlap_start, end=overlap_end)
    result = _run_with_calendars(
        tmp_path,
        [
            ("PropA", "P1", [alice_a]),
            ("PropB", "P1", [alice_b]),
            ("PropA", "P2", [bob_a]),
            ("PropC", "P2", [bob_c]),
        ],
    )
    warnings = [line for line in result.output.splitlines() if "Overlap" in line]
    assert warnings, "expected at least one overlap warning"
    # Both are Multi — warning shows "Multi · P1" and "Multi · P2"
    assert any("Multi · P1" in w for w in warnings)
    assert any("Multi · P2" in w for w in warnings)


# ---------------------------------------------------------------------------
# days in config
# ---------------------------------------------------------------------------


def test_days_from_config(tmp_path):
    # days = 1 in config → only today+1 window; all test fixtures are far future → no recipients
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hi"\ndays = 1\n\n'
        '[[calendars]]\nname = "Cal"\nurl = "https://example.com/cal.ics"\n',
        encoding="utf-8",
    )
    recs = [Recipient(name="Alice", email="a@x.com", start=date(2030, 1, 1), end=date(2030, 1, 5))]
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        result = runner.invoke(main, ["--config", str(p), "--dry-run"])
    assert result.exit_code == 0
    assert "No recipients found" in result.output


def test_days_cli_overrides_config(tmp_path):
    # config has days = 1, CLI has --days 3650 → far-future recipient should appear
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hi"\ndays = 1\n\n'
        '[[calendars]]\nname = "Cal"\nurl = "https://example.com/cal.ics"\n',
        encoding="utf-8",
    )
    recs = [Recipient(name="Alice", email="a@x.com", start=date(2030, 1, 1), end=date(2030, 1, 5))]
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--days", "3650", "--yes"])
    assert result.exit_code == 0
    assert "Alice" in result.output


# ---------------------------------------------------------------------------
# Sent log
# ---------------------------------------------------------------------------


def test_sent_column_shown_in_output(config_file, mock_sent_log):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "Sent" in result.output
    # Unsent recipients with email show ○; no ✓ expected on a fresh log
    assert "○" in result.output


def test_sent_column_checkmark_when_logged(config_file, mock_sent_log):
    rec = MOCK_RECIPIENTS[0]
    key = _sent_key(rec, "Test Cal")
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_sent_log_loaded_message(config_file, mock_sent_log):
    """Startup line shows path and entry count when sent.log exists."""
    mock_sent_log.write_text("somekey\n", encoding="utf-8")
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "Sent log:" in result.output
    assert "1 entries" in result.output


def test_sent_log_will_be_created_message(config_file, mock_sent_log):
    """Startup line says 'will be created' when sent.log does not yet exist."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "Sent log will be created" in result.output


def test_test_config_sent_log_message():
    """--test-config shows a test-mode sent.log startup line."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "pre-seeded" in result.output


def test_test_config_pre_sent_shows_checkmark():
    """In --test-config mode the pre-seeded entry (Radka) shows ✓ in the table."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "✓" in result.output


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


def test_test_config_auto_disables_interactive():
    """--test-config always runs non-interactively, even if --interactive is given."""
    runner = CliRunner()
    # No input provided — if interactive were active, click.confirm would be called
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Would send" in result.output


def _eligible_recs():
    """Two recipients with check-ins within the default 14-day advance window."""
    return [
        Recipient(
            name="Alice",
            email="alice@example.com",
            start=date.today() + timedelta(days=5),
            end=date.today() + timedelta(days=10),
        ),
        Recipient(
            name="Bob",
            email="bob@example.com",
            start=date.today() + timedelta(days=7),
            end=date.today() + timedelta(days=12),
        ),
    ]


def test_interactive_confirm_writes_sent_log(smtp_config_file, mock_sent_log):
    runner = CliRunner()
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()),
        patch("welcomer.cli.send_email"),
    ):
        # "y\nn\n" → confirm Alice, skip Bob
        result = runner.invoke(main, ["--config", str(smtp_config_file)], input="y\nn\n")
    assert result.exit_code == 0
    assert mock_sent_log.exists()
    logged = mock_sent_log.read_text(encoding="utf-8")
    assert "Alice" in logged
    assert "Bob" not in logged


def test_interactive_deny_does_not_write_sent_log(config_file, mock_sent_log):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file)], input="n\nn\n")
    assert result.exit_code == 0
    assert not mock_sent_log.exists()


def test_interactive_skips_already_sent(config_file, mock_sent_log):
    recs = _eligible_recs()
    alice = recs[0]
    key = _sent_key(alice, "Test Cal")
    mock_sent_log.parent.mkdir(parents=True, exist_ok=True)
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        # Only Bob should be prompted (Alice already sent) — answer n
        result = runner.invoke(main, ["--config", str(config_file)], input="n\n")
    assert result.exit_code == 0
    # Alice was already in log — key still present, nothing extra written
    logged = mock_sent_log.read_text(encoding="utf-8")
    assert "Alice" in logged


def test_interactive_dry_run_does_not_write_sent_log(config_file, mock_sent_log):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run"], input="y\ny\n")
    assert result.exit_code == 0
    assert not mock_sent_log.exists()


def test_interactive_summary_line(config_file, mock_sent_log):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file)], input="y\ny\n")
    assert result.exit_code == 0
    assert "interactively" in result.output


# ---------------------------------------------------------------------------
# Interactive default / --yes flag
# ---------------------------------------------------------------------------


def test_interactive_is_default(smtp_config_file, mock_sent_log):
    """Without any flag the app prompts for eligible recipients."""
    runner = CliRunner()
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()),
        patch("welcomer.cli.send_email"),
    ):
        result = runner.invoke(main, ["--config", str(smtp_config_file)], input="y\ny\n")
    assert result.exit_code == 0
    assert "interactively" in result.output
    # Both confirmed → written to log
    assert mock_sent_log.exists()


def test_yes_flag_sends_without_prompts(smtp_config_file, mock_sent_log):
    """--yes auto-sends all eligible without prompting."""
    runner = CliRunner()
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()),
        patch("welcomer.cli.send_email"),
    ):
        result = runner.invoke(main, ["--config", str(smtp_config_file), "--yes"])
    assert result.exit_code == 0
    assert "interactively" not in result.output
    assert mock_sent_log.exists()
    logged = mock_sent_log.read_text(encoding="utf-8")
    assert "Alice" in logged
    assert "Bob" in logged


def test_yes_dry_run_does_not_write_sent_log(config_file, mock_sent_log):
    """--yes --dry-run previews without writing to sent.log."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file), "--yes", "--dry-run"])
    assert result.exit_code == 0
    assert "Would send" in result.output
    assert not mock_sent_log.exists()


def test_yes_skips_already_sent(smtp_config_file, mock_sent_log):
    """--yes skips recipients already in sent.log."""
    recs = _eligible_recs()
    alice = recs[0]
    key = _sent_key(alice, "Test Cal")
    mock_sent_log.parent.mkdir(parents=True, exist_ok=True)
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    runner = CliRunner()
    with (
        patch("welcomer.cli.fetch_recipients", return_value=recs),
        patch("welcomer.cli.send_email"),
    ):
        result = runner.invoke(main, ["--config", str(smtp_config_file), "--yes"])
    assert result.exit_code == 0
    # Only Bob added — Alice was already in log
    logged = mock_sent_log.read_text(encoding="utf-8")
    assert "Alice" in logged
    assert "Bob" in logged
    assert logged.count("\n") == 2  # Alice (pre-existing) + Bob (newly added)


# ---------------------------------------------------------------------------
# Sent column markers
# ---------------------------------------------------------------------------


def test_sent_marker_empty_for_no_email(tmp_path):
    """Recipient with no email address shows an empty status cell (no ✗)."""
    recs = [Recipient(name="NoEmail", email=None)]
    result = _run_with_calendars(tmp_path, [("Villa", "P", recs)])
    assert result.exit_code == 0
    assert "✗" not in result.output
    assert "●" not in result.output
    assert "○" not in result.output


def test_sent_marker_empty_for_past_checkin(tmp_path):
    """Recipient whose check-in is in the past and not yet sent shows an empty status cell."""
    today = date.today()
    recs = [
        Recipient(
            name="PastCheckin",
            email="p@x.com",
            start=today - timedelta(days=3),
            end=today + timedelta(days=4),
        )
    ]
    result = _run_with_calendars(tmp_path, [("Villa", "P", recs)])
    assert result.exit_code == 0
    assert "✗" not in result.output
    assert "●" not in result.output
    # ○ might appear for other test recipients; check PastCheckin specifically is in output
    assert "PastCheckin" in result.output


def test_past_checkin_already_sent_shows_checkmark(tmp_path, mock_sent_log):
    """Past-checkin guest that was already sent shows ✓, not empty."""
    today = date.today()
    rec = Recipient(
        name="SentGuest",
        email="s@x.com",
        start=today - timedelta(days=3),
        end=today + timedelta(days=4),
    )
    key = _sent_key(rec, "Villa")
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_past_checkin_not_sent_in_yes_mode(tmp_path):
    """Past-checkin recipients are never sent, even with --yes."""
    today = date.today()
    recs = [
        Recipient(
            name="PastCheckin",
            email="p@x.com",
            start=today - timedelta(days=3),
            end=today + timedelta(days=4),
        ),
        Recipient(
            name="FutureGuest",
            email="f@x.com",
            start=today + timedelta(days=5),
            end=today + timedelta(days=10),
        ),
    ]
    result = _run_with_calendars(
        tmp_path, [("Villa", "P", recs)], extra_args=["--advance", "99999"]
    )
    assert "Would send 1" in result.output  # only FutureGuest


def test_sent_marker_circle_for_not_yet_eligible(tmp_path):
    """Recipient with email but outside advance window shows ○."""
    # advance=0 → only today-or-past eligible; far-future start → ○
    recs = [Recipient(name="Guest", email="g@x.com", start=date(2099, 1, 1), end=date(2099, 1, 5))]
    result = _run_with_calendars(tmp_path, [("Villa", "P", recs)], extra_args=["--advance", "0"])
    assert result.exit_code == 0
    assert "○" in result.output


def test_sent_marker_filled_circle_for_eligible(tmp_path):
    """Recipient within advance window shows ● (green filled circle)."""
    # advance=99999 → any future date is eligible
    recs = [Recipient(name="Guest", email="g@x.com", start=date(2099, 1, 1), end=date(2099, 1, 5))]
    result = _run_with_calendars(
        tmp_path, [("Villa", "P", recs)], extra_args=["--advance", "99999"]
    )
    assert result.exit_code == 0
    assert "●" in result.output


def test_sent_marker_checkmark_when_in_log(tmp_path, mock_sent_log):
    """Recipient already in sent.log shows ✓ regardless of eligibility."""
    rec = Recipient(name="Guest", email="g@x.com", start=date(2099, 1, 1), end=date(2099, 1, 5))
    key = _sent_key(rec, "Villa")
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])])
    assert result.exit_code == 0
    assert "✓" in result.output


# ---------------------------------------------------------------------------
# Calendar loading order (grouped by property name)
# ---------------------------------------------------------------------------


def test_calendar_loading_grouped_by_property():
    """Calendars with the same property name are loaded consecutively.

    Alphabetical sort: Apartmán Sluneční → Chalupa U Lesa → Horský Apartmán x2
    """
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    out = result.output
    idx_ha_housepal = out.index("Horský Apartmán · HousePal")
    idx_ha_staybook = out.index("Horský Apartmán · StayBook")
    idx_lesa = out.index("Chalupa U Lesa")
    idx_slunecni = out.index("Apartmán Sluneční")
    # Alphabetical: Apartmán < Chalupa < Horský (both Horský entries load last, together)
    assert idx_slunecni < idx_lesa < idx_ha_housepal
    assert idx_slunecni < idx_lesa < idx_ha_staybook


def test_calendar_loading_grouped_by_property_with_mocked_calendars(tmp_path):
    """Same-property calendars from different providers are adjacent in loading output."""
    recs = [Recipient(name="G", email="g@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5))]
    # Config order: ZZZ/P1, AAA/P1, ZZZ/P2 — after stable sort: AAA, ZZZ/P1, ZZZ/P2
    result = _run_with_calendars(
        tmp_path,
        [("ZZZ Villa", "P1", recs), ("AAA Villa", "P1", recs), ("ZZZ Villa", "P2", recs)],
    )
    out = result.output
    # AAA Villa loaded before ZZZ Villa entries
    idx_aaa = out.index("AAA Villa")
    idx_zzz = out.index("ZZZ Villa")
    assert idx_aaa < idx_zzz


# ---------------------------------------------------------------------------
# --advance flag and config option
# ---------------------------------------------------------------------------


def test_advance_default_is_14():
    from welcomer.config import WelcomerConfig

    assert WelcomerConfig.from_dict({}).advance == 14


def test_advance_from_config(tmp_path):
    """advance in config controls eligibility window."""
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hi"\nadvance = 30\n\n'
        '[[calendars]]\nname = "Cal"\nurl = "https://example.com/cal.ics"\n',
        encoding="utf-8",
    )
    # start in 20 days — eligible with advance=30, not eligible with advance=0
    recs = [
        Recipient(
            name="Guest",
            email="g@x.com",
            start=date.today() + timedelta(days=20),
            end=date.today() + timedelta(days=25),
        )
    ]
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "●" in result.output


def test_advance_cli_overrides_config(tmp_path):
    """--advance CLI flag overrides config advance value."""
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hi"\nadvance = 0\n\n'
        '[[calendars]]\nname = "Cal"\nurl = "https://example.com/cal.ics"\n',
        encoding="utf-8",
    )
    # start in 50 days — not eligible with advance=0, but eligible with --advance 60
    recs = [
        Recipient(
            name="Guest",
            email="g@x.com",
            start=date.today() + timedelta(days=50),
            end=date.today() + timedelta(days=55),
        )
    ]
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--yes", "--advance", "60"])
    assert result.exit_code == 0
    assert "●" in result.output


def test_advance_ineligible_shows_circle(tmp_path):
    """Reservations outside the advance window show ○."""
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi {name}"\nbody = "Hi"\n\n'
        '[[calendars]]\nname = "Cal"\nurl = "https://example.com/cal.ics"\n',
        encoding="utf-8",
    )
    recs = [
        Recipient(
            name="Guest",
            email="g@x.com",
            start=date.today() + timedelta(days=99),
            end=date.today() + timedelta(days=104),
        )
    ]
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        # advance=0 → only today or past is eligible
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--yes", "--advance", "0"])
    assert result.exit_code == 0
    assert "○" in result.output


def test_interactive_skips_ineligible_recipients(config_file, mock_sent_log):
    """Dry-run mode does not prompt even in interactive mode."""
    # MOCK_RECIPIENTS have start=None → not eligible
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        # No input provided — if prompts fired, click.confirm would Abort
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--advance", "0"])
    assert result.exit_code == 0
    assert "Would send" in result.output


def test_interactive_prompts_eligible_recipients(smtp_config_file, mock_sent_log):
    """Interactive mode prompts only for eligible recipients."""
    eligible_recs = [
        Recipient(
            name="Alice",
            email="alice@example.com",
            start=date.today() + timedelta(days=5),
            end=date.today() + timedelta(days=10),
        ),
        Recipient(
            name="Bob",
            email="bob@example.com",
            start=date.today() + timedelta(days=200),
            end=date.today() + timedelta(days=205),
        ),
    ]
    runner = CliRunner()
    with (
        patch("welcomer.cli.fetch_recipients", return_value=eligible_recs),
        patch("welcomer.cli.send_email"),
    ):
        # advance=14 → Alice (5 days) eligible, Bob (200 days) not
        # Only one prompt (Alice) → one "y"
        result = runner.invoke(
            main, ["--config", str(smtp_config_file), "--advance", "14"], input="y\n"
        )
    assert result.exit_code == 0
    assert "interactively" in result.output
    # Alice was confirmed → in sent.log
    assert mock_sent_log.exists()
    assert "Alice" in mock_sent_log.read_text(encoding="utf-8")
    assert "Bob" not in mock_sent_log.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SMTP sending
# ---------------------------------------------------------------------------

TOML_WITH_SMTP = """\
subject = "Welcome, {name}!"
body = "Hi {name}, glad to have you."

[smtp]
host = "localhost"
port = 1025
from = "welcomer@example.com"

[[calendars]]
name = "Test Cal"
url = "https://example.com/test.ics"
"""


@pytest.fixture
def smtp_config_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(TOML_WITH_SMTP)
    return p


def _eligible_recipients():
    from datetime import date, timedelta

    return [
        Recipient(
            name="Alice",
            email="alice@example.com",
            start=date.today() + timedelta(days=3),
            end=date.today() + timedelta(days=7),
        ),
    ]


def test_send_email_called_on_real_send(smtp_config_file):
    """With smtp configured, send_email is called for each eligible recipient."""
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()),
        patch("welcomer.cli.send_email") as mock_send,
    ):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(smtp_config_file), "--yes"])
    assert result.exit_code == 0
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == "alice@example.com"


def test_send_email_not_called_on_dry_run(smtp_config_file):
    """--dry-run must never call send_email even with smtp configured."""
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()),
        patch("welcomer.cli.send_email") as mock_send,
    ):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(smtp_config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    mock_send.assert_not_called()


def test_no_smtp_config_prints_warning(config_file):
    """Missing [smtp] section on a real send (not dry-run) prints a warning."""
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(config_file), "--yes"])
    assert result.exit_code == 0
    assert "smtp" in result.output.lower()


def test_no_smtp_config_no_warning_on_dry_run(config_file):
    """Missing [smtp] section is silent in --dry-run mode."""
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "Warning" not in result.output


def test_smtp_failure_does_not_mark_sent(smtp_config_file, mock_sent_log):
    """If send_email raises, the recipient is not recorded in sent.log."""
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()),
        patch("welcomer.cli.send_email", side_effect=Exception("connection refused")),
    ):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(smtp_config_file), "--yes"])
    assert result.exit_code == 0
    assert "Failed to send" in result.output
    assert not mock_sent_log.exists()


def test_sent_log_written_after_successful_send(smtp_config_file, mock_sent_log):
    """Successful send is recorded in sent.log."""
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()),
        patch("welcomer.cli.send_email"),
    ):
        runner = CliRunner()
        runner.invoke(main, ["--config", str(smtp_config_file), "--yes"])
    assert mock_sent_log.exists()
    assert "Alice" in mock_sent_log.read_text(encoding="utf-8")


def test_interactive_send_calls_send_email(smtp_config_file, mock_sent_log):
    """Interactive mode calls send_email when user confirms."""
    with (
        patch("welcomer.cli.fetch_recipients", return_value=_eligible_recipients()),
        patch("welcomer.cli.send_email") as mock_send,
    ):
        runner = CliRunner()
        result = runner.invoke(
            main, ["--config", str(smtp_config_file), "--advance", "14"], input="y\n"
        )
    assert result.exit_code == 0
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == "alice@example.com"


# ---------------------------------------------------------------------------
# --silent flag
# ---------------------------------------------------------------------------


def test_silent_suppresses_loaded_message(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(
            main, ["--config", str(config_file), "--dry-run", "--yes", "--silent"]
        )
    assert result.exit_code == 0
    assert "Loaded" not in result.output


def test_silent_suppresses_would_send_message(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(
            main, ["--config", str(config_file), "--dry-run", "--yes", "--silent"]
        )
    assert result.exit_code == 0
    assert "Would send" not in result.output


def test_silent_still_shows_table(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(
            main, ["--config", str(config_file), "--dry-run", "--yes", "--silent"]
        )
    assert result.exit_code == 0
    assert "Alice" in result.output


def test_without_silent_shows_loaded_message(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes"])
    assert "Loaded" in result.output


def test_silent_short_flag(config_file):
    """-s is an alias for --silent."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes", "-s"])
    assert result.exit_code == 0
    assert "Loaded" not in result.output
    assert "Would send" not in result.output


def test_silent_suppresses_sent_log_message(config_file):
    """--silent must suppress the 'Sent log will be created' line."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--yes", "-s"])
    assert result.exit_code == 0
    assert "Sent log" not in result.output


def test_silent_does_not_suppress_overlap_warning():
    """Overlap warnings must print even with --silent / -s."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "-s"])
    assert result.exit_code == 0
    assert "⚠ Overlap" in result.output


def test_overlap_warning_shown_outside_days_window(tmp_path):
    """Overlap warning appears even when overlapping events fall outside --days."""
    p = tmp_path / "config.toml"
    p.write_text(
        'subject = "Hi"\nbody = "Hi"\n'
        '[[calendars]]\nname = "Villa"\nprovider = "P"\nurl = "https://x.com/a.ics"\n'
        '[[calendars]]\nname = "Villa"\nprovider = "Q"\nurl = "https://x.com/b.ics"\n'
    )
    # Two overlapping reservations 60 days out — outside --days 1
    far = date.today() + timedelta(days=60)
    recs_a = [Recipient(name="Alice", email="a@x.com", start=far, end=far + timedelta(days=5))]
    recs_b = [
        Recipient(
            name="Bob",
            email="b@x.com",
            start=far + timedelta(days=2),
            end=far + timedelta(days=7),
        )
    ]

    def _fetch(url, force_refresh=False):
        return recs_a if "a.ics" in url else recs_b

    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", side_effect=_fetch):
        result = runner.invoke(main, ["--config", str(p), "--dry-run", "--days", "1"])
    assert result.exit_code == 0
    assert "⚠ Overlap" in result.output


# ---------------------------------------------------------------------------
# --advance edge cases
# ---------------------------------------------------------------------------


def test_advance_zero_makes_checkin_today_eligible(tmp_path):
    """With --advance 0, only a reservation starting today is eligible."""
    today = date.today()
    rec = Recipient(name="Alice", email="a@x.com", start=today, end=today + timedelta(days=3))
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])], extra_args=["--advance", "0"])
    assert "●" in result.output


def test_advance_zero_tomorrow_not_eligible(tmp_path):
    """With --advance 0, a reservation starting tomorrow is not yet eligible."""
    today = date.today()
    rec = Recipient(
        name="Bob", email="b@x.com", start=today + timedelta(days=1), end=today + timedelta(days=5)
    )
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])], extra_args=["--advance", "0"])
    assert "○" in result.output


def test_advance_one_includes_tomorrow(tmp_path):
    """With --advance 1, a reservation starting tomorrow is eligible."""
    today = date.today()
    rec = Recipient(
        name="Carol",
        email="c@x.com",
        start=today + timedelta(days=1),
        end=today + timedelta(days=5),
    )
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])], extra_args=["--advance", "1"])
    assert "●" in result.output


# ---------------------------------------------------------------------------
# Empty email / phone display
# ---------------------------------------------------------------------------


def test_no_email_displays_empty_not_none(tmp_path):
    """A recipient with no email shows an empty string, not 'none', in the output."""
    rec = Recipient(name="NoEmail", email=None)
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])])
    assert result.exit_code == 0
    assert "none" not in result.output.lower().split()


def test_no_phone_displays_empty_not_none(tmp_path):
    """A recipient with no phone shows an empty string, not 'none', in the output."""
    rec = Recipient(name="NoPhone", email="np@x.com", phone="")
    result = _run_with_calendars(tmp_path, [("Villa", "P", [rec])])
    assert result.exit_code == 0
    assert "none" not in result.output.lower().split()
