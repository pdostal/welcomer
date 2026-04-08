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
uv run welcomer --config ~/.config/welcomer/config.toml --dry-run

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

# Release (creates GitHub release + PyPI package + container tags automatically)
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
   (markdown template), `days` (optional filter), `send_without_email` (bool), and a list of
   `CalendarConfig` (url + property + official_name + provider).

1. **`ical.py`** — fetches each calendar URL with `httpx`, parses with `icalendar`, and returns
   `Recipient` objects (name, email, phone, start, end, extra). Extracts from `ATTENDEE` entries;
   falls back to `ORGANIZER`; last resort uses `SUMMARY` + `Description` parsing (`Email:`,
   `Telefon:`). Phone is extracted from `Description` for all paths. Remote fetches are cached via
   `cache.py`.

1. **`cache.py`** — disk cache for remote iCal URLs. Stores raw `.ics` bytes in
   `~/.config/welcomer/cache/<sha256-of-url>.ics`. TTL is 5 hours (checked via `mtime`). Provides
   `get_cached(url)` and `save_cache(url, data)`; both accept an optional `cache_dir` override (used
   in tests).

1. **`smtp.py`** — email sending via stdlib `smtplib`. Single function
   `send_email(cfg, to, subject, body)`. Supports plain SMTP, STARTTLS (`tls=true`), and SSL
   (`ssl=true`). Authenticates only when `cfg.username` is set. Formats `From` as
   `"from_name <from_addr>"` when `from_name` is set. Adds CC header when `cfg.cc` is set; BCC
   addresses are included in the SMTP envelope only (not in message headers). When `to` is empty
   (send_without_email mode), sends to CC/BCC only; skips send entirely if no recipients. Body is
   sent as plain text (the rendered markdown template).

1. **`core.py`** — calls `_render()` to render Jinja2 templates with guest context variables
   (`name`, `email`, `phone`, `start`, `end`, `adults`, `kids`, `property`, `official_name`,
   `provider`, `summary`) into `subject`/`body`, producing `WelcomeResult` objects. Uses a shared
   `jinja2.Environment` with `autoescape=False` and `undefined=jinja2.Undefined` (unknown variables
   silently render as empty string).

**`cli.py`** wires it all together via Click. Default output: one compact line per recipient (name,
dates, email, phone, sent status). Add `--print-note` to also render the subject and markdown body.
Markdown rendered via `rich.Markdown`.

## Config format

Config is loaded from the first path that exists, in priority order:

1. `config.toml` in the current working directory
1. `~/.config/welcomer/config.toml`

Both paths are excluded from git. Create one of these files (see README.md for an example). Keys:
`subject`, `body` (multiline TOML string, markdown), `days` (optional int), `send_without_email`
(bool, default false), `[[calendars]]` array with `url`, `property` (accommodation name; `name` is
also accepted for backward compat), `official_name` (optional legal name), and `provider`.

Message templates use Jinja2 syntax (`{{ variable }}`, `{% if %}...{% endif %}`, filters). Available
variables: `name`, `email`, `phone`, `start`, `end`, `adults`, `kids`, `property`, `official_name`
(falls back to `property`), `provider`, `summary`. Unknown variables render as empty string. See
README.md for the full variable table and Jinja2 usage examples.

## CLI flags

- `--config / -c PATH` — override config file path
- `--dry-run` — preview output, don't send
- `--test-config` — use bundled test data with 4 properties and 8 events (requires `--dry-run`;
  automatically runs non-interactively)
- `--yes` — auto-send all eligible emails without prompting; records sends in
  `~/.config/welcomer/sent.log`; skips already-sent and not-yet-eligible reservations
- `--days N` — only show reservations starting within N days; overrides `days` in config
- `--advance N` — days before check-in when a reservation becomes eligible to send (default: 14);
  overrides `advance` in config
- `--print-note` — also render subject + markdown body per guest
- `--force-refresh` — bypass the 5-hour calendar cache and re-fetch all remote URLs; no effect on
  local file paths or `--test-config`
- `--silent / -s` — suppress informational output (loaded/sent messages); overlap warnings still
  print

## SMTP config

Add an `[smtp]` section to enable actual sending. Without it, the app runs in preview-only mode and
prints a warning on non-dry-run invocations.

```toml
[smtp]
host = "smtp.example.com"
port = 587
from = "info@myproperty.com"
from_name = "My Property"           # optional: display name in From header
# cc = ["manager@myproperty.com"]  # optional: CC on every email (list or single string)
# bcc = ["audit@myproperty.com"]   # optional: BCC (envelope only, not in headers)
username = "info@myproperty.com"   # omit for unauthenticated relay
password = "secret"
tls = true    # STARTTLS (port 587)
# ssl = true  # SSL/TLS (port 465)
```

For local testing use **Mailpit** (`brew install mailpit`): SMTP on port 1025, web UI on
`http://localhost:8025`.

If `send_email` raises, the recipient is **not** added to `sent.log` (no false positives).

## Sent log

`~/.config/welcomer/sent.log` — one line per confirmed send, format:
`{property}|{start}|{end}|{name}|{email}`. Created automatically.

The `Sent` column in the output table shows one of four states:

| Symbol | Colour | Meaning | | ------ | ------ | ------- | | `✓` | green | Already sent (in
sent.log) | | `●` | green | Eligible to send now (today ≤ check-in ≤ today + advance days) | | `○` |
yellow | Not yet eligible (check-in too far in the future) | | (empty) | — | No email address
(unless `send_without_email = true`), or check-in already passed and not yet sent |

When `send_without_email = true`, reservations without a guest email show `○`/`●` and are sent to
CC/BCC recipients only (requires CC or BCC configured in `[smtp]`).

Emails are never sent to reservations whose check-in date is in the past — those guests have either
already arrived or departed. If a welcome was sent before check-in, the row shows `✓`; if it was
never sent, the status cell is empty.

## Test fixtures

- `tests/fixtures/cal.ics` — real e-chalupy.cz reservation calendar (2 guests, used in ical tests)
- `src/welcomer/data/cal.ics` — same file, packaged as resource (kept in sync with tests/fixtures)
- `src/welcomer/data/testdata.py` — programmatic test data for `--test-config`; dates are always
  relative to `date.today()` so they never go stale. Four properties (Horský Apartmán/HousePal,
  Horský Apartmán/StayBook, Chalupa U Lesa/HousePal, Apartmán Sluneční/StayBook) with 9 events
  total. Horský Apartmán always has an overlap between HousePal and StayBook. Tomáš Procházka
  appears on two properties via the same provider and merges into a "Multi" entry. Klára Novotná is
  always in-progress (checked in 3 days ago). Radka Horáčková is pre-seeded as already sent. Exposes
  `get_test_calendars()`, `get_pre_sent_key()`, and `TEST_CONFIG`.

When updating any fixture, copy to both `tests/fixtures/` and `src/welcomer/data/`.

## Container

Published to `ghcr.io/pdostal/welcomer`. Built from `Dockerfile` (multi-stage: uv builder →
`python:3.14-slim` runtime). Use podman to run:

```sh
podman run --rm \
  -v ~/.config/welcomer:/root/.config/welcomer:ro \
  ghcr.io/pdostal/welcomer --dry-run
```

Tags: `latest` (master), `X.Y.Z` and `X.Y` (on version tags).

## CI

GitHub Actions on every push/PR: **Lint**, **Test**, **Build** (parallel). On `v*` tags: **Publish**
(container → ghcr.io) then **GitHub release** (body from `CHANGELOG.md`). Dependabot updates pip,
GitHub Actions, and Docker base image weekly.
