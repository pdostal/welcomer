# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Commands

```sh
# Run the app
uv run welcomer --help
uv run welcomer --dry-run
uv run welcomer --dry-run --test-config    # use bundled test config + fixtures, no network needed
uv run welcomer --dry-run --print-note      # also show rendered subject + body
uv run welcomer --config ~/.config/welcomer.toml --dry-run

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

# Release (creates GitHub release + container tags automatically)
# 1. bump version in pyproject.toml
# 2. add ## [X.Y.Z] section to CHANGELOG.md
# 3. commit, tag, push:
git tag vX.Y.Z && git push && git push origin vX.Y.Z
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

## CLI flags

- `--config / -c PATH` — override config file path
- `--dry-run` — preview output, don't send
- `--test-config` — use bundled `src/welcomer/data/test_config.toml` + 3 property ICS fixtures (requires `--dry-run`)
- `--print-note` — also render subject + markdown body per guest

## Test fixtures

- `tests/fixtures/cal.ics` — real e-chalupy.cz reservation calendar (2 guests, used in ical tests)
- `src/welcomer/data/cal.ics` — same file, packaged as resource (kept in sync with tests/fixtures)
- `tests/fixtures/tipsy_gnome_napHub.ics`, `biscuit_chateau_snoozePal.ics`, `snoring_goat_snoozePal.ics` — 3 test calendars (The Tipsy Gnome/NapHub, Château du Biscuit/SnoozePal, The Snoring Goat/SnoozePal; 2 guests each, 2026 dates). Referenced directly by `--test-config` at runtime.
- `src/welcomer/data/test_config.toml` — bundled test config referencing the 3 property ICS files

When updating any fixture, copy to both `tests/fixtures/` and `src/welcomer/data/`.

## Container

Published to `ghcr.io/pdostal/welcomer`. Built from `Dockerfile` (multi-stage: uv builder →
`python:3.14-slim` runtime). Use podman to run:

```sh
podman run --rm \
  -v ~/.config/welcomer.toml:/root/.config/welcomer.toml:ro \
  ghcr.io/pdostal/welcomer --dry-run
```

Tags: `latest` (master), `X.Y.Z` and `X.Y` (on version tags).

## CI

GitHub Actions on every push/PR: **Lint**, **Test**, **Build** (parallel). On `v*` tags: **Publish**
(container → ghcr.io) then **GitHub release** (body from `CHANGELOG.md`). Dependabot updates pip,
GitHub Actions, and Docker base image weekly.
