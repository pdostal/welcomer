# welcomer

Sends configurable welcome emails to guests loaded from iCal calendar URLs. Built for accommodation
businesses — reads reservations from a calendar and emails each guest a personalised welcome
message.

## Container

```sh
podman run --rm \
  -v ~/.config/welcomer.toml:/root/.config/welcomer.toml:ro \
  ghcr.io/pdostal/welcomer --dry-run
```

`latest` is updated on every push to `master`. Tagged releases follow `vX.Y.Z`.

## Setup

```sh
brew install uv taplo
uv sync
cp config.example.toml config.toml
# edit config.toml and add your calendar URL
```

## Usage

```sh
uv run welcomer --dry-run              # preview recipients list
uv run welcomer --dry-run --print-note # also show rendered message per guest
uv run welcomer                        # send
uv run welcomer --dry-run --test-calendar  # test with bundled sample calendar
```

## Config

Config is loaded from the first path that exists:

1. `config.toml` in the current directory
1. `~/.config/welcomer.toml`

Example (`config.example.toml`):

```toml
subject = "Reservation confirmed – {name}"
body = """
Dear {name},

Thank you for your reservation from {start} to {end}.
"""

[[calendars]]
name = "Reservations"
url = "https://example.com/calendar.ics"
```

Template variables: `{name}`, `{email}`, `{phone}`, `{start}`, `{end}`, `{summary}`.

## Recipient extraction

Recipients are extracted from calendar events in this order:

1. `ATTENDEE` entries
1. `ORGANIZER` if no attendees
1. `SUMMARY` (name) + `Description` field (email via `Email:`, phone via `Telefon:`) as last resort

Phone and email parsed from `Description` are available in all three cases.
