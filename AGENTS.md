# AGENTS.md

## Repo Shape

- Python package in `src/welcomer`; CLI entrypoint is `welcomer.cli:main`.
- `config.py` loads TOML config from the first existing path: `config.toml` in the cwd, then
  `~/.config/welcomer/config.toml`.
- Remote iCal fetches are cached for 5 hours in `~/.config/welcomer/cache/`; local file paths and
  `--test-config` bypass cache.
- Confirmed sends are recorded in `~/.config/welcomer/sent.log`.

## High-Signal Commands

- Install dev deps: `uv sync --group dev`
- Run app: `uv run welcomer --dry-run`
- Use bundled fixtures: `uv run welcomer --dry-run --test-config`
- Single test: `uv run pytest tests/test_ical.py::test_attendees_extracted`
- Full test suite: `uv run pytest -v`
- Lint/format checks: `uv run ruff check .`, `uv run black --check .`, `taplo fmt --check`,
  `uv run mdformat --check --exclude ".venv/**" --exclude ".pytest_cache/**" .`
- Build: `uv build`

## Working Rules

- Treat `README.md` and `CLAUDE.md` as the main repo docs; if they conflict with code or CI, trust
  the executable config and workflows.
- CI runs lint, test, and build separately in GitHub Actions.
- Keep the mirrored fixture files in sync when editing test ICS data: `tests/fixtures/cal.ics` and
  `src/welcomer/data/cal.ics`.
- Config uses `[[message]]` for named subject/body templates and `[[calendar]]` for calendars; each
  calendar must reference a valid message name.
- The app uses Jinja2 templates with undefined variables rendering as empty string.
- `send_without_email = true` only works when CC or BCC is configured in `[smtp]`.

## Before Changing Behaviour

- Check `README.md`, `CLAUDE.md`, `pyproject.toml`, and `.github/workflows/*` first for the current
  source of truth.
- Prefer the smallest change that matches the existing CLI and test style.
