"""Tests for the CLI."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from welcomer.cli import main
from welcomer.ical import Recipient

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


def test_test_calendar_dry_run(config_file):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--dry-run", "--test-calendar"])
    assert result.exit_code == 0
    assert "test calendar" in result.output
    assert "Josef" in result.output
    assert "Would send" in result.output


def test_test_calendar_requires_dry_run(config_file):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--test-calendar"])
    assert result.exit_code == 2
    assert "--test-calendar requires --dry-run" in result.output


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
