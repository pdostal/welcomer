# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
