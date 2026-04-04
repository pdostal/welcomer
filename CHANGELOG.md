# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Aligned tabular output** — columns (Name, From, To, Duration, Calendar, E-mail, Phone) with
  emoji headers; sorted by start date → end date → property → provider
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
  `X.Y.Z` and `X.Y` semver tags on releases
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
