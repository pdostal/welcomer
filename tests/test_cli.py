"""Tests for the CLI."""

import pytest
from click.testing import CliRunner

from welcomer.cli import main


TOML_CONTENT = """\
title = "Test Welcome"
message = "Hi {name}!"
channels = ["#test"]

[[recipients]]
name = "Alice"

[[recipients]]
name = "Bob"
"""


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
    result = runner.invoke(main, ["--config", str(config_file), "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "Would send" in result.output


def test_normal_run(config_file):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file)])
    assert result.exit_code == 0
    assert "Sent" in result.output
    assert "Alice" in result.output
    assert "Bob" in result.output


def test_missing_config():
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "nonexistent.toml"])
    assert result.exit_code == 1


def test_title_override(config_file):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--title", "Override Title"])
    assert result.exit_code == 0
    assert "Override Title" in result.output


def test_recipient_override(config_file):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--recipient", "Carol"])
    assert result.exit_code == 0
    assert "Carol" in result.output
