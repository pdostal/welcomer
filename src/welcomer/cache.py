"""Disk cache for remote iCal URLs.

Cache files are stored in ``~/.config/welcomer/cache/`` as
``<sha256-of-url>.ics``.  A cached file is considered fresh for
:data:`CACHE_TTL` seconds (default 5 hours); older files are ignored and
overwritten on the next fetch.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".config" / "welcomer" / "cache"
CACHE_TTL = 5 * 60 * 60  # 5 hours in seconds


def _cache_path(url: str, cache_dir: Path) -> Path:
    key = hashlib.sha256(url.encode()).hexdigest()
    return cache_dir / f"{key}.ics"


def get_cached(url: str, cache_dir: Path = CACHE_DIR) -> bytes | None:
    """Return cached bytes for *url*, or ``None`` if missing or expired."""
    path = _cache_path(url, cache_dir)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL:
        return None
    return path.read_bytes()


def save_cache(url: str, data: bytes, cache_dir: Path = CACHE_DIR) -> None:
    """Write *data* to the cache for *url*, creating directories as needed."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(url, cache_dir).write_bytes(data)
