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
# copy the example config below to config.toml and edit it
```

## Usage

```sh
uv run welcomer --dry-run              # preview recipients list
uv run welcomer --dry-run --print-note # also show rendered message per guest
uv run welcomer                        # interactive send (default)
uv run welcomer --yes                  # send to all without prompting
uv run welcomer --yes --silent         # send silently (suppress info messages)
uv run welcomer --dry-run --test-config  # test with bundled sample calendars
```

## Config

Config is loaded from the first path that exists:

1. `config.toml` in the current directory
1. `~/.config/welcomer/config.toml`

Example config:

```toml
subject = "Reservation confirmed – {name}"

# Only show reservations starting within this many days from today (optional)
# days = 30

# Days before check-in when a reservation becomes eligible to send (default: 14)
# advance = 14

body = """
Dear {name},

Thank you for your reservation from {start} to {end}.
We look forward to hosting you ({adults} adults, {kids} kids).
"""

[smtp]
host = "smtp.example.com"
port = 587
from = "info@myproperty.com"
username = "info@myproperty.com"
password = "secret"
tls = true      # use STARTTLS (port 587)
# ssl = true    # use SSL/TLS instead (port 465)

[[calendars]]
name = "My Property"
provider = "BookingProvider"
url = "https://example.com/calendar.ics"
```

Template variables: `{name}`, `{email}`, `{phone}`, `{start}`, `{end}`, `{summary}`, `{adults}`,
`{kids}`.

## Local SMTP testing with Mailpit

**[Mailpit](https://mailpit.axllent.org/)** catches outgoing emails locally without actually
delivering them. It gives you a web inbox at `http://localhost:8025` and listens for SMTP on port
1025 — no account, no real delivery, no risk of accidentally mailing guests.

```sh
brew install mailpit
mailpit                  # starts in the foreground; Ctrl-C to stop
```

Mailpit also runs as a macOS service if you prefer:

```sh
brew services start mailpit
```

Add this to your config while testing:

```toml
[smtp]
host = "localhost"
port = 1025
from = "test@localhost"
# no username / password / tls needed for Mailpit
```

Then run welcomer as normal — all emails land in the Mailpit inbox at `http://localhost:8025`
instead of being delivered.

## Interactive mode

Interactive mode is on by default. The app prompts before sending each eligible email (check-in
within the `advance` window, default 14 days). Use `--yes` to skip prompts. Previously sent
reservations are tracked in `~/.config/welcomer/sent.log` and skipped automatically on future runs.

The `Sent` column shows the status of each reservation:

| Symbol | Colour | Meaning | | ------ | ------ | ------- | | `✓` | green | Already sent (in
sent.log) | | `●` | green | Eligible to send now (check-in within advance window) | | `○` | yellow |
Not yet eligible (check-in too far away) | | (empty) | — | No email address, or check-in already
passed and not yet sent |

## Calendar cache

Remote iCal URLs are cached for **5 hours** in `~/.config/welcomer/cache/`. This avoids hitting your
calendar provider on every run. Use `--force-refresh` to bypass the cache and re-fetch all remote
URLs immediately:

```sh
uv run welcomer --dry-run --force-refresh
```

The cache directory is created automatically. Each URL is stored as a separate `<sha256-of-url>.ics`
file. Local file paths and `--test-config` are never cached.

## Multi-property reservations

When the same guest (identical name, provider, check-in, and check-out) appears across multiple
properties, welcomer merges them into a single **Multi** entry and sends one email. The property
column shows `Multi` and overlapping reservations from other providers are still detected correctly.

## Overlap detection

welcomer warns when two reservations for the same property have overlapping dates. Warnings appear
above the table regardless of the `--days` filter. Affected rows are highlighted in red.

## Recipient extraction

Recipients are extracted from calendar events in this order:

1. `ATTENDEE` entries
1. `ORGANIZER` if no attendees
1. `SUMMARY` (name) + `Description` field (email via `Email:`, phone via `Telefon:`) as last resort

Phone and email parsed from `Description` are available in all three cases.
