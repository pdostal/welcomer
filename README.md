# welcomer

Sends configurable welcome messages to recipients loaded from iCal calendar URLs.

## Setup

```sh
brew install uv taplo
uv sync
cp config.example.toml config.toml
# edit config.toml and add your calendar URLs
```

## Usage

```sh
uv run welcomer --dry-run   # preview
uv run welcomer             # send
```

## Config

`config.toml` (see `config.example.toml`):

```toml
subject = "Welcome, {name}!"
body = """
Hi {name} <{email}>, your period is {start} – {end}.
"""

[[calendars]]
name = "Onboarding"
url = "https://example.com/calendar.ics"
```

Recipients, names, emails, and date periods are extracted from `ATTENDEE` entries in each calendar's
events.
