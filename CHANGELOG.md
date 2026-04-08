# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-04-08

### Added

- **Jinja2 templates** — subject and body now use Jinja2 syntax (`{{ variable }}`,
  `{% if %}...{% endif %}`, filters); conditionals, filters, and the `or` shorthand are all
  supported; unknown variables silently render as empty string
- **`official_name` template variable** — legal/official property name; falls back to `property`
  when not set; multi-property reservations get a comma-separated list
- **`from_name` SMTP option** — sets the display name in the `From` header
  (`"My Property <info@example.com>"`)
- **`cc` and `bcc` SMTP options** — CC is added to message headers; BCC is included in the SMTP
  envelope only (not visible to recipients); both accept a list or a single string
- **`send_without_email` config flag** — when `true`, reservations without a guest email still show
  `○`/`●` and are sent to CC/BCC recipients only
- **Interactive prompting for missing contact data** — in interactive mode the app asks for email
  and phone before rendering the template, so they can be used as template variables
- **`official_name` calendar field** — add `official_name = "..."` to any `[[calendars]]` entry

### Changed

- `CalendarConfig.name` renamed to `CalendarConfig.property` for consistency; `name =` in TOML is
  still accepted (backward compat)
- Column header "🏡 Calendar" → "🏡 Property"
- Template syntax changed from Python `str.format_map` (`{name}`) to Jinja2 (`{{ name }}`);
  **existing configs must be updated**

## [0.4.1] - 2026-04-06

### Added

- **PyPI package** — `pip install welcomer` / `uv tool install welcomer`
- **MIT licence** — `LICENSE` file added

### Fixed

- Phone numbers with spaces (e.g. `+420 608 901 234`) are now stripped to `+420608901234` on both
  parse and display
- Reservations that ended before today are now always hidden, even without `--days`; checkout-today
  (end == today) remains visible

## [0.4.0] - 2026-04-05

### Added

- **Multi-property merging** — when the same guest (identical name, provider, check-in, and
  check-out) appears across multiple properties, they are merged into a single **Multi** entry and
  only one welcome email is sent
- **In-progress reservations shown** — reservations that have already started but not yet ended are
  included in the output; checkout-today reservations are included too
- **Active reservations highlighted in blue** — guest name shown in blue when check-in ≤ today ≤
  check-out (ongoing stay), green otherwise
- **`--silent / -s` flag** — suppresses informational messages (loaded, would-send, sent-log);
  overlap warnings always print regardless
- **Overlap detection extended to Multi entries** — a Multi guest's constituent properties are each
  checked for conflicts against other providers; the warning shows `Multi · provider` for merged
  entries and `Property · provider` for single-property entries

### Changed

- Past-check-in guests never receive a welcome email; the `Sent` cell shows `✓` if previously sent
  or empty if not (was `✗` for no-email, now consistently empty for both no-email and past-check-in)
- Overlap warning date range separator changed from `–` to `→`

### Removed

- `✗` sent-status marker replaced by an empty cell

## [0.3.0] - 2026-04-03

### Added

- **`--yes` flag** — auto-sends all eligible welcome emails without prompting; writes to
  `~/.config/welcomer/sent.log` (skips already-sent entries). Use with `--dry-run` to preview what
  would be sent
- **`--advance` flag and config option** — days before check-in when a reservation becomes eligible
  (default: 14); controls which reservations the interactive and `--yes` modes act on
- **Interactive mode** (default) — prompts before each eligible send; records confirmed sends in
  `~/.config/welcomer/sent.log`; skips already-sent entries automatically
- **`Sent` column** in the output table with 4-state markers: `✓` (sent), `●` (eligible, not yet
  sent), `○` (not yet eligible), `✗` (no email)
- **Overlap detection** — warns when two reservations for the same property have overlapping dates;
  affected rows shown in red
- **Config path moved** to `~/.config/welcomer/config.toml` (previously `~/.config/welcomer.toml`)

### Removed

- `--non-interactive` flag replaced by `--yes`

## [0.2.0] - 2026-04-03

### Added

- **`--test-config` flag** — replaces `--test-calendar`; loads a bundled test config with 3
  fictional properties (The Tipsy Gnome/NapHub, Biscuit Château/SnoozePal, The Snoring
  Goat/SnoozePal) and 6 guests across 3 ICS fixtures
- **`provider` field** on `[[calendars]]` config entries; `{provider}` template variable available
  in subject/body
- **`{property}` template variable** — set from the calendar `name` field
- **`--property` and `--provider` filters** — case-insensitive substring match; skip calendars that
  don't match
- **`--days N` filter** — only show reservations starting within N days from today (inactive by
  default)
- **`date_format` config field** — strftime format string for date display (default `%Y-%m-%d`);
  test config uses `%d. %m. %Y`
- **Aligned tabular output** — columns (Name, From, To, Duration, Calendar, email, Phone) with emoji
  headers; sorted by start date → end date → property → provider
- **Path support in calendar `url`** — accepts absolute and relative file paths in addition to
  HTTP(S) URLs; relative paths resolve against the config file's directory
- **Expanded test suite** — sort order, sort tiebreakers, filter edge cases, `--days` with mocked
  today

### Changed

- `--test-calendar` renamed to `--test-config`

## [0.1.1] - 2026-04-02

### Added

- **Accommodation business focus** — guest name from `SUMMARY`, email and phone (`Telefon:`)
  extracted from the `Description` field (e-chalupy.cz calendar format)
- **XDG config path** — `~/.config/welcomer.toml` used as fallback when local `config.toml` is
  absent; `config.toml` in the current directory still takes priority
- **Phone support** — `{phone}` template variable; falls back to `unknown` when not found
- **Compact coloured output** — one line per guest: bold-green name, cyan dates, blue email, phone
- **`--print-note` flag** — optionally render the full subject and message body per guest
- **`--test-calendar` flag** — preview output using the bundled sample calendar (requires
  `--dry-run`)
- **OCI container** — image published to `ghcr.io/pdostal/welcomer`; `latest` on every master push,
  `X.Y.Z` and `X.Y` SemVer tags on releases
- **Expanded test suite** — unit tests for `_to_date`, `_parse_email`, `_extract_cn`,
  `fetch_recipients`, and fixture-based tests against a real e-chalupy.cz calendar file

### Changed

- `config.example.toml` rewritten for accommodation/hospitality use case
- README rewritten to reflect the accommodation business context and Docker usage

## [0.1.0] - 2026-04-01

### Added

- Initial release: fetch iCal calendar URLs, extract recipients from `ATTENDEE` / `ORGANIZER`
  entries, render a configurable subject and markdown body per recipient
- `--dry-run` mode, `--config` flag, Rich terminal output
- GitHub Actions CI (lint, test, build) and Dependabot
