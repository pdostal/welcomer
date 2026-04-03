"""Tests for the CLI."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from welcomer.cli import main
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
        result = runner.invoke(main, ["--config", str(p), "--dry-run", *extra_args])
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
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run"])
    assert result.exit_code == 0
    assert "Would send" in result.output
    assert "Alice" in result.output


def test_normal_run(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file)])
    assert result.exit_code == 0
    assert "Sent" in result.output
    assert "Alice" in result.output
    assert "Bob" in result.output


def test_print_note(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--print-note"])
    assert result.exit_code == 0
    assert "Welcome, Alice!" in result.output  # rendered subject shown


def test_no_note_by_default(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file), "--dry-run"])
    assert "glad to have you" not in result.output  # body not shown by default


def test_missing_config():
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "nonexistent.toml"])
    assert result.exit_code == 1


def test_default_config_uses_xdg(tmp_path):
    """When no local config.toml exists, the XDG path is used as default."""
    xdg_config = tmp_path / "welcomer.toml"
    xdg_config.write_text(TOML_CONTENT)
    local_missing = tmp_path / "config.toml"  # does not exist
    runner = CliRunner()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local_missing),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg_config),
        patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS),
    ):
        result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Sent" in result.output


def test_default_config_uses_local(tmp_path):
    """When local config.toml exists it takes priority over the XDG path."""
    local_config = tmp_path / "config.toml"
    local_config.write_text(TOML_CONTENT)
    xdg_config = tmp_path / "welcomer.toml"  # does not exist
    runner = CliRunner()
    with (
        patch("welcomer.config.LOCAL_CONFIG_PATH", local_config),
        patch("welcomer.config.XDG_CONFIG_PATH", xdg_config),
        patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS),
    ):
        result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Sent" in result.output


def test_test_config_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Martina" in result.output
    assert "Would send" in result.output


def test_test_config_requires_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["--test-config"])
    assert result.exit_code == 2
    assert "--test-config requires --dry-run" in result.output


def test_property_filter():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "Tipsy Gnome"])
    assert result.exit_code == 0
    assert "Martina" in result.output
    assert "Anna" not in result.output
    assert "Radka" not in result.output


def test_property_filter_case_insensitive():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config", "--property", "tipsy gnome"])
    assert result.exit_code == 0
    assert "Martina" in result.output
    assert "Anna" not in result.output


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
    # Martina starts 2026-05-03 (30 days from 2026-04-03), others are further out
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "30"])
    assert result.exit_code == 0
    assert "Martina" in result.output
    assert "Lukáš" not in result.output


def test_days_filter_not_active_by_default():
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    assert result.exit_code == 0
    assert "Would send 6" in result.output


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_sort_full_order_by_start_date():
    # Fixture order: Martina (May 3) → Radka (May 22) → Anna (Jun 1)
    #               → Lukáš (Jul 15) → Pavel (Aug 20) → Jiří (Sep 5)
    runner = CliRunner()
    result = runner.invoke(main, ["--dry-run", "--test-config"])
    out = result.output
    assert (
        out.index("Martina")
        < out.index("Radka")
        < out.index("Anna")
        < out.index("Lukáš")
        < out.index("Pavel")
        < out.index("Jiří")
    )


def test_sort_by_end_date_when_same_start(tmp_path):
    # Beta has same start but later end → should come after Alpha
    recs = [
        Recipient(name="Beta", email="b@x.com", start=date(2026, 6, 1), end=date(2026, 6, 10)),
        Recipient(name="Alpha", email="a@x.com", start=date(2026, 6, 1), end=date(2026, 6, 5)),
    ]
    result = _run_with_calendars(tmp_path, [("Cal", "Prov", recs)])
    assert result.output.index("Alpha") < result.output.index("Beta")


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
    assert result.output.index("Guest2") < result.output.index("Guest1")


# ---------------------------------------------------------------------------
# --days filter
# ---------------------------------------------------------------------------


def test_days_filter_boundary_inclusive():
    # Martina starts exactly 30 days from today → must be included
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 4, 3))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "30"])
    assert "Martina" in result.output


def test_days_filter_excludes_past():
    # Mock today = 2026-06-15: Martina (May 3), Radka (May 22), Anna (Jun 1) are past
    runner = CliRunner()
    with patch("welcomer.cli.date", _mock_today(date(2026, 6, 15))):
        result = runner.invoke(main, ["--dry-run", "--test-config", "--days", "365"])
    assert "Lukáš" in result.output
    assert "Martina" not in result.output
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
    good_recipients = [Recipient(name="Alice", email="alice@example.com")]

    def side_effect(url):
        if "good" in url:
            return good_recipients
        raise Exception("unreachable")

    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", side_effect=side_effect):
        result = runner.invoke(main, ["--config", str(p)])
    assert result.exit_code == 0
    assert "Failed to load" in result.output
    assert "Sent 1" in result.output


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()
