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
    assert "dry run" in result.output
    assert "Would send" in result.output


def test_normal_run(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", return_value=MOCK_RECIPIENTS):
        result = runner.invoke(main, ["--config", str(config_file)])
    assert result.exit_code == 0
    assert "Sent" in result.output
    assert "Alice" in result.output
    assert "Bob" in result.output


def test_missing_config():
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "nonexistent.toml"])
    assert result.exit_code == 1


def test_fetch_failure(config_file):
    runner = CliRunner()
    with patch("welcomer.cli.fetch_recipients", side_effect=Exception("timeout")):
        result = runner.invoke(main, ["--config", str(config_file)])
    assert "Failed to load" in result.output
    assert result.exit_code == 0
