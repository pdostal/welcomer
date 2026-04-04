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
    with patch("welcomer.cli.fetch_recipients", side_effect=lambda u: url_map.get(u, [])):
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
    # NapHub (Tipsy Gnome) has real reservations but no contact info — shown with "none"
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "Tipsy Gnome"])
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_property_filter_case_insensitive():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "tipsy gnome"])
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
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "SnoozePal"])
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Radka" in result.output
    assert "Martina" not in result.output


def test_provider_filter_case_insensitive():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "snoozepal"])
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Martina" not in result.output


def test_property_and_provider_filter_combined():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--dry-run", "--test-config", "--property", "Château", "--provider", "SnoozePal"],
    )
    assert result.exit_code == 0
    assert "Anna" in result.output
    assert "Radka" not in result.output
    assert "Martina" not in result.output


def _mock_today(d: date):
    m = MagicMock()
    m.today.return_value = d
    return m


def test_days_filter_excludes_far_future():
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "1"])
    assert result.exit_code == 0
    assert "No recipients found" in result.output


def test_days_filter_includes_upcoming():
    # Within 50 days from 2026-04-03 (cutoff 2026-05-23): Radka (May 22) yes, Anna (Jun 1) no
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "50"])
    assert result.exit_code == 0
    assert "Radka" in result.output
    assert "Anna" not in result.output


def test_days_filter_not_active_by_default():
    # Only SnoozePal calendars expose guest contact info (4 guests: Anna, Pavel, Radka, Jiří)
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Would send 4" in result.output


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_sort_full_order_by_start_date():
    # SnoozePal guests only (NapHub exports no contact info):
    # Radka (May 22) → Anna (Jun 1) → Pavel (Aug 20) → Jiří (Sep 5)
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    # Search only within the table (overlap warnings may reference names before the table)
    table = result.output[result.output.index("👤 Name") :]
    assert table.index("Radka") < table.index("Anna") < table.index("Pavel") < table.index("Jiří")


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
    # Radka starts 2026-05-22, which is exactly 49 days from 2026-04-03 → must be included
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "49"])
    assert "Radka" in result.output


def test_days_filter_excludes_past():
    # Mock today = 2026-06-15: Radka (May 22) and Anna (Jun 1) are past; Pavel/Jiří are future
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 6, 15))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "365"])
    assert "Pavel" in result.output
    assert "Jiří" in result.output
    assert "Radka" not in result.output
    assert "Anna" not in result.output


def test_days_filter_combined_with_property():
    # days=100 from 2026-04-03 → cutoff 2026-07-12
    # --property Snoring → only The Snoring Goat (Radka May 22, Jiří Sep 5)
    # Radka is within 100 days, Jiří is not
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(
            main, ["--dry-run", "--test-config", "--days", "100", "--property", "Snoring"]
        )
    assert result.exit_code == 0
    assert "Radka" in result.output
    assert "Jiří" not in result.output
    assert "Martina" not in result.output


def test_days_zero_shows_only_today(tmp_path):
    today = date(2026, 6, 1)
    recs = [
        Recipient(name="Today", email="t@x.com", start=today, end=date(2026, 6, 5)),
        Recipient(name="Tomorrow", email="tm@x.com", start=date(2026, 6, 2), end=date(2026, 6, 6)),
    ]
    with patch("welcomer.cli.date", _mock_today(today)):
        result = _run_with_calendars(tmp_path, [("Cal", "Prov", recs)], extra_args=["--days", "0"])
    assert "Today" in result.output
    assert "Tomorrow" not in result.output


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

    def side_effect(url):
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
# NapHub (Biscuit Château) filter
# ---------------------------------------------------------------------------


def test_biscuit_chateau_napHub_filter():
    # NapHub has real reservations but no contact info — shown with "none", nothing sent
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--dry-run", "--test-config", "--property", "Château", "--provider", "NapHub"],
    )
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_napHub_provider_no_guests_to_send():
    # NapHub has real reservations but no contact info — shown in table, nothing sent
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--provider", "NapHub"])
    assert result.exit_code == 0
    assert "Reservation" in result.output
    assert "Would send 0" in result.output


def test_closed_events_shown_but_not_sent():
    """CLOSED events from booking.com-style calendars appear in the table but are not sent."""
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "CLOSED" in result.output
    assert "Would send 4" in result.output


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------


def test_overlap_detected_in_test_config():
    # NapHub Reservation (Jun 7–15) overlaps Anna Dvořáková/SnoozePal (Jun 1–10)
    # at Biscuit Château — overlapping Jun 7–10
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Overlap" in result.output
    assert "Biscuit Château" in result.output
    assert "Reservation" in result.output
    assert "Anna" in result.output


def test_overlap_shows_both_providers():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert "NapHub" in result.output
    assert "SnoozePal" in result.output


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


def test_interactive_confirm_writes_sent_log(config_file, mock_sent_log):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        # "y\nn\n" → confirm Alice, skip Bob
        result = runner.invoke(main, ["--config", str(config_file)], input="y\nn\n")
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


def test_interactive_is_default(config_file, mock_sent_log):
    """Without any flag the app prompts for eligible recipients."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file)], input="y\ny\n")
    assert result.exit_code == 0
    assert "interactively" in result.output
    # Both confirmed → written to log
    assert mock_sent_log.exists()


def test_yes_flag_sends_without_prompts(config_file, mock_sent_log):
    """--yes auto-sends all eligible without prompting."""
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=_eligible_recs()):
        result = runner.invoke(main, ["--config", str(config_file), "--yes"])
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


def test_yes_skips_already_sent(config_file, mock_sent_log):
    """--yes skips recipients already in sent.log."""
    recs = _eligible_recs()
    alice = recs[0]
    key = _sent_key(alice, "Test Cal")
    mock_sent_log.parent.mkdir(parents=True, exist_ok=True)
    mock_sent_log.write_text(key + "\n", encoding="utf-8")
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=recs):
        result = runner.invoke(main, ["--config", str(config_file), "--yes"])
    assert result.exit_code == 0
    # Only Bob added — Alice was already in log
    logged = mock_sent_log.read_text(encoding="utf-8")
    assert "Alice" in logged
    assert "Bob" in logged
    assert logged.count("\n") == 2  # Alice (pre-existing) + Bob (newly added)


# ---------------------------------------------------------------------------
# Sent column markers
# ---------------------------------------------------------------------------


def test_sent_marker_red_x_for_no_email(tmp_path):
    """Recipient with no email address shows ✗ in the Sent column."""
    recs = [Recipient(name="NoEmail", email=None)]
    result = _run_with_calendars(tmp_path, [("Villa", "P", recs)])
    assert result.exit_code == 0
    assert "✗" in result.output


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

    Original order: Tipsy Gnome, Biscuit Château/SnoozePal, Snoring Goat, Biscuit Château/NapHub
    After stable sort by name: Biscuit Château x2 → Snoring Goat → Tipsy Gnome
    """
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    out = result.output
    # Both Biscuit Château entries appear before The Snoring Goat and The Tipsy Gnome
    idx_bc1 = out.index("Biscuit Château · SnoozePal")
    idx_bc2 = out.index("Biscuit Château · NapHub")
    idx_goat = out.index("The Snoring Goat")
    idx_gnome = out.index("The Tipsy Gnome")
    assert idx_bc1 < idx_goat
    assert idx_bc2 < idx_goat
    assert idx_bc1 < idx_gnome
    assert idx_bc2 < idx_gnome


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
    """Interactive mode does not prompt for recipients outside the advance window."""
    # MOCK_RECIPIENTS have start=None → not eligible
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        # No input provided — if prompts fired, click.confirm would Abort
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--advance", "0"])
    assert result.exit_code == 0
    assert "interactively" in result.output


def test_interactive_prompts_eligible_recipients(config_file, mock_sent_log):
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
    with patch("welcomer.cli.fetch_recipients", return_value=eligible_recs):
        # advance=14 → Alice (5 days) eligible, Bob (200 days) not
        # Only one prompt (Alice) → one "y"
        result = runner.invoke(main, ["--config", str(config_file), "--advance", "14"], input="y\n")
    assert result.exit_code == 0
    assert "interactively" in result.output
    # Alice was confirmed → in sent.log
    assert mock_sent_log.exists()
    assert "Alice" in mock_sent_log.read_text(encoding="utf-8")
    assert "Bob" not in mock_sent_log.read_text(encoding="utf-8")
