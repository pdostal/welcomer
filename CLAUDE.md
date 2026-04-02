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

## Purpose

Accommodation business tool. Reads guest reservations from iCal calendar URLs and sends each guest a
personalised welcome email. The test fixture (`tests/fixtures/cal.ics`, `src/welcomer/data/cal.ics`)
uses the e-chalupy.cz format where guest name is in `SUMMARY` and contact details (email, phone) are
embedded in the `Description` field.

## Architecture

The app loads iCal calendar URLs from config, extracts recipients from calendar events, renders a
subject + markdown body per recipient, and prints the result.

Data flows through three layers:

1. **`config.py`** — loads `config.toml` (TOML) into `WelcomerConfig`, which holds `subject`, `body`
   (markdown template), and a list of `CalendarConfig` (url + name).

1. **`ical.py`** — fetches each calendar URL with `httpx`, parses with `icalendar`, and returns
   `Recipient` objects (name, email, phone, start, end, extra). Extracts from `ATTENDEE` entries;
   falls back to `ORGANIZER`; last resort uses `SUMMARY` + `Description` parsing (`Email:`,
   `Telefon:`). Phone is extracted from `Description` for all paths.

1. **`core.py`** — calls `_render()` to interpolate `{name}`, `{email}`, `{phone}`, `{start}`,
   `{end}`, `{summary}` into `subject`/`body`, producing `WelcomeResult` objects.

**`cli.py`** wires it all together via Click. Default output: one compact line per recipient (name,
dates, email, phone). Add `--print-note` to also render the subject and markdown body. Markdown
rendered via `rich.Markdown`.

## Config format

Config is loaded from the first path that exists, in priority order:

1. `config.toml` in the current working directory
1. `~/.config/welcomer.toml`

Both paths are excluded from git. Copy `config.example.toml` to either location and edit it. Keys:
`subject`, `body` (multiline TOML string, markdown), `[[calendars]]` array with `url` and `name`.

Message template variables: `{name}`, `{email}`, `{phone}`, `{start}`, `{end}`, `{summary}`.

## CI

GitHub Actions runs three parallel jobs on every push/PR: **Lint**, **Test**, **Build**. Dependabot
updates pip and action versions weekly.
