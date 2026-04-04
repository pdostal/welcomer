# welcomer

Sends configurable welcome emails to guests loaded from iCal calendar URLs. Built for accommodation
businesses — reads reservations from a calendar and emails each guest a personalised welcome
message.

## Container

```sh
podman run --rm \
  -v ~/.config/welcomer:/root/.config/welcomer:ro \
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
uv run welcomer                        # interactive send (default)
uv run welcomer --non-interactive      # send to all without prompting
uv run welcomer --dry-run --test-config  # test with bundled sample calendars
```

## Config

Config is loaded from the first path that exists:

1. `config.toml` in the current directory
1. `~/.config/welcomer/config.toml`

Example (`config.example.toml`):

```toml
subject = "Reservation confirmed – {name}"

# Only show reservations starting within this many days from today (optional)
# days = 30

# Days before check-in when a reservation becomes eligible to send (default: 14)
# advance = 14

body = """
Dear {name},

Thank you for your reservation from {start} to {end}.
"""

[[calendars]]
name = "Reservations"
url = "https://example.com/calendar.ics"
```

Template variables: `{name}`, `{email}`, `{phone}`, `{start}`, `{end}`, `{summary}`.

## Interactive mode

Interactive mode is on by default. The app prompts before sending each eligible email (check-in
within the `advance` window, default 14 days). Use `--non-interactive` to skip prompts. Previously
sent reservations are tracked in `~/.config/welcomer/sent.log` and skipped automatically on future
runs.

The `Sent` column shows the status of each reservation:

| Symbol | Colour | Meaning | | ------ | ------ | ------- | | `✓` | green | Already sent | | `●` |
green | Eligible to send now (check-in within advance window) | | `○` | yellow | Not yet eligible
(check-in too far away) | | `✗` | red | No email address |

## Recipient extraction

Recipients are extracted from calendar events in this order:

1. `ATTENDEE` entries
1. `ORGANIZER` if no attendees
1. `SUMMARY` (name) + `Description` field (email via `Email:`, phone via `Telefon:`) as last resort

Phone and email parsed from `Description` are available in all three cases.
