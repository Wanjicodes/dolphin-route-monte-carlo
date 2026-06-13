"""
cache.py
────────
Local CSV cache layer for API responses.

Why this exists:
- Avoids hitting rate-limited APIs on every simulation run
- Makes development faster (no waiting for network)
- Provides offline fallback
- Production DE pattern: cache → curated → consumed

Cache strategy: time-based expiry (default 24h).
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta


CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(key: str) -> Path:
    """Return the file path for a given cache key."""
    safe_key = key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe_key}.json"


def get_cached(key: str, ttl_hours: int = 24):
    """
    Retrieve cached data if it exists and is fresh.
    
    Parameters
    ----------
    key : str — unique identifier for this dataset
    ttl_hours : int — how long the cache is valid
    
    Returns
    -------
    dict or None — cached data, or None if missing/expired
    """
    path = _cache_path(key)
    if not path.exists():
        return None

    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > ttl_hours * 3600:
        return None  # Expired

    with open(path, "r") as f:
        cached = json.load(f)

    return cached


def set_cache(key: str, data: dict):
    """Save data to cache."""
    path = _cache_path(key)
    payload = {
        "cached_at": datetime.now().isoformat(),
        "data": data,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)


def clear_cache(key: str = None):
    """Clear specific cache key, or all if key is None."""
    if key:
        path = _cache_path(key)
        if path.exists():
            path.unlink()
    else:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()


def cache_info():
    """Return info on all cached items."""
    items = []
    for f in CACHE_DIR.glob("*.json"):
        age_hours = (time.time() - f.stat().st_mtime) / 3600
        items.append({
            "key": f.stem,
            "age_hours": round(age_hours, 1),
            "size_kb": round(f.stat().st_size / 1024, 2),
        })
    return items