"""Tests for the disk-based iCal cache."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from welcomer.cache import CACHE_TTL, _cache_path, get_cached, save_cache
from welcomer.ical import fetch_recipients

SAMPLE_URL = "https://example.com/calendar.ics"
SAMPLE_DATA = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"


# ---------------------------------------------------------------------------
# cache_path
# ---------------------------------------------------------------------------


def test_cache_path_is_deterministic(tmp_path):
    assert _cache_path(SAMPLE_URL, tmp_path) == _cache_path(SAMPLE_URL, tmp_path)


def test_cache_path_differs_for_different_urls(tmp_path):
    assert _cache_path(SAMPLE_URL, tmp_path) != _cache_path("https://other.com/cal.ics", tmp_path)


def test_cache_path_has_ics_extension(tmp_path):
    assert _cache_path(SAMPLE_URL, tmp_path).suffix == ".ics"


# ---------------------------------------------------------------------------
# save_cache / get_cached
# ---------------------------------------------------------------------------


def test_get_cached_returns_none_when_missing(tmp_path):
    assert get_cached(SAMPLE_URL, cache_dir=tmp_path) is None


def test_save_then_get_returns_data(tmp_path):
    save_cache(SAMPLE_URL, SAMPLE_DATA, cache_dir=tmp_path)
    assert get_cached(SAMPLE_URL, cache_dir=tmp_path) == SAMPLE_DATA


def test_save_creates_cache_directory(tmp_path):
    deep = tmp_path / "a" / "b"
    save_cache(SAMPLE_URL, SAMPLE_DATA, cache_dir=deep)
    assert deep.is_dir()


def test_get_cached_returns_none_when_expired(tmp_path):
    save_cache(SAMPLE_URL, SAMPLE_DATA, cache_dir=tmp_path)
    path = _cache_path(SAMPLE_URL, tmp_path)
    # backdate mtime beyond TTL
    old_time = time.time() - CACHE_TTL - 1
    import os

    os.utime(path, (old_time, old_time))
    assert get_cached(SAMPLE_URL, cache_dir=tmp_path) is None


def test_get_cached_returns_data_when_fresh(tmp_path):
    save_cache(SAMPLE_URL, SAMPLE_DATA, cache_dir=tmp_path)
    # mtime is just now — should still be fresh
    assert get_cached(SAMPLE_URL, cache_dir=tmp_path) == SAMPLE_DATA


def test_save_cache_overwrites_existing(tmp_path):
    save_cache(SAMPLE_URL, b"old", cache_dir=tmp_path)
    save_cache(SAMPLE_URL, b"new", cache_dir=tmp_path)
    assert get_cached(SAMPLE_URL, cache_dir=tmp_path) == b"new"


# ---------------------------------------------------------------------------
# fetch_recipients — cache integration
# ---------------------------------------------------------------------------

ICAL_BYTES = b"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Test Event
DTSTART;VALUE=DATE:20260401
DTEND;VALUE=DATE:20260408
ATTENDEE;CN="Alice":mailto:alice@example.com
END:VEVENT
END:VCALENDAR
"""


def test_fetch_recipients_writes_cache(tmp_path):
    mock_response = MagicMock()
    mock_response.content = ICAL_BYTES
    with (
        patch("httpx.get", return_value=mock_response),
        patch("welcomer.ical.save_cache") as mock_save,
        patch("welcomer.ical.get_cached", return_value=None),
    ):
        fetch_recipients(SAMPLE_URL)
    mock_save.assert_called_once_with(SAMPLE_URL, ICAL_BYTES)


def test_fetch_recipients_uses_cache_on_hit(tmp_path):
    with (
        patch("welcomer.ical.get_cached", return_value=ICAL_BYTES) as mock_get,
        patch("httpx.get") as mock_http,
    ):
        result = fetch_recipients(SAMPLE_URL)
    mock_get.assert_called_once_with(SAMPLE_URL)
    mock_http.assert_not_called()
    assert len(result) == 1
    assert result[0].name == "Alice"


def test_fetch_recipients_skips_cache_on_force_refresh():
    mock_response = MagicMock()
    mock_response.content = ICAL_BYTES
    with (
        patch("httpx.get", return_value=mock_response) as mock_http,
        patch("welcomer.ical.get_cached") as mock_get,
        patch("welcomer.ical.save_cache"),
    ):
        fetch_recipients(SAMPLE_URL, force_refresh=True)
    mock_get.assert_not_called()
    mock_http.assert_called_once()


def test_fetch_recipients_overwrites_cache_on_force_refresh():
    mock_response = MagicMock()
    mock_response.content = ICAL_BYTES
    with (
        patch("httpx.get", return_value=mock_response),
        patch("welcomer.ical.get_cached"),
        patch("welcomer.ical.save_cache") as mock_save,
    ):
        fetch_recipients(SAMPLE_URL, force_refresh=True)
    mock_save.assert_called_once_with(SAMPLE_URL, ICAL_BYTES)


def test_fetch_recipients_cache_miss_hits_network():
    mock_response = MagicMock()
    mock_response.content = ICAL_BYTES
    with (
        patch("welcomer.ical.get_cached", return_value=None),
        patch("httpx.get", return_value=mock_response) as mock_http,
        patch("welcomer.ical.save_cache"),
    ):
        fetch_recipients(SAMPLE_URL)
    mock_http.assert_called_once()
