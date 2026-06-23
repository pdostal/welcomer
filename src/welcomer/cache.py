"""Disk cache for remote iCal URLs.

Cache files are stored in ``~/.config/welcomer/cache/`` as
``<UTC timestamp>_<sha256-of-url>.ics``.  A cached file is considered fresh for
:data:`CACHE_TTL` seconds (default 5 hours); older files are ignored and left
on disk.
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

CACHE_DIR = Path.home() / ".config" / "welcomer" / "cache"
CACHE_TTL = 5 * 60 * 60  # 5 hours in seconds


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _cache_path(url: str, cache_dir: Path, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d%H%M%S")
    return cache_dir / f"{timestamp}_{_cache_key(url)}.ics"


def _cached_paths(url: str, cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.glob(f"*_{_cache_key(url)}.ics"), reverse=True)


def get_cached(url: str, cache_dir: Path = CACHE_DIR) -> bytes | None:
    """Return cached bytes for *url*, or ``None`` if missing or expired."""
    if not cache_dir.exists():
        return None
    paths = _cached_paths(url, cache_dir)
    if not paths:
        return None
    path = paths[0]
    if time.time() - path.stat().st_mtime > CACHE_TTL:
        return None
    return path.read_bytes()


def save_cache(url: str, data: bytes, cache_dir: Path = CACHE_DIR) -> None:
    """Write *data* to the cache for *url*, creating directories as needed."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(url, cache_dir).write_bytes(data)
