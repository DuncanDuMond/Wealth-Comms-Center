"""
cache.py — local JSON cache for expensive chart calculations.

Uses pathlib throughout (per your standing preference) so this works
unmodified on Windows/OneDrive paths as well as Linux.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Optional

DEFAULT_CACHE_DIR = Path.home() / ".wealth_agent_cache"


class ChartCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _make_key(birth_date: str, birth_time: str, lat: float, lon: float) -> str:
        raw = f"{birth_date}|{birth_time}|{lat:.6f}|{lon:.6f}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, birth_date: str, birth_time: str, lat: float, lon: float) -> Optional[dict]:
        key = self._make_key(birth_date, birth_time, lat, lon)
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, birth_date: str, birth_time: str, lat: float, lon: float, data: dict[str, Any]) -> None:
        key = self._make_key(birth_date, birth_time, lat, lon)
        path = self._path_for(key)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
