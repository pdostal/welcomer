# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Commands

```sh
# Run the app
uv run welcomer --help
uv run welcomer --dry-run

# Tests
uv run pytest -v
uv run pytest tests/test_ical.py::test_attendees_extracted   # single test

# Linters (all must pass before committing)
uv run ruff check .
uv run ruff check --fix .
uv run black .
taplo fmt
uv run mdformat --exclude ".venv/**" --exclude ".pytest_cache/**" .
uv run --with yamllint yamllint .

# Build
uv build
```

## Architecture

The app loads iCal calendar URLs from config, extracts recipients from calendar events, renders a
subject + markdown body per recipient, and prints the result.

Data flows through three layers:

1. **`config.py`** — loads `config.toml` (TOML) into `WelcomerConfig`, which holds `subject`, `body`
   (markdown template), and a list of `CalendarConfig` (url + name).

1. **`ical.py`** — fetches each calendar URL with `httpx`, parses with `icalendar`, and returns
   `Recipient` objects (name, email, start, end, extra). Extracts from `ATTENDEE` entries; falls
   back to `ORGANIZER` if none.

1. **`core.py`** — calls `_render()` to interpolate `{name}`, `{email}`, `{start}`, `{end}`,
   `{summary}` into `subject`/`body`, producing `WelcomeResult` objects.

**`cli.py`** wires it all together via Click. It's the only place that does I/O (HTTP fetches + Rich
console output). Markdown body is rendered via `rich.Markdown`.

## Config format

`config.toml` is excluded from git (copy from `config.example.toml`). Keys: `subject`, `body`
(multiline TOML string, markdown), `[[calendars]]` array with `url` and `name`.

Message template variables: `{name}`, `{email}`, `{start}`, `{end}`, `{summary}`.

## CI

GitHub Actions runs three parallel jobs on every push/PR: **Lint**, **Test**, **Build**. Dependabot
updates pip and action versions weekly.
