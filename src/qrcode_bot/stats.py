from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
STATS_FILE = DATA_DIR / "stats.json"


def _load() -> dict[str, Any]:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"generated": 0, "decoded": 0, "wifi": 0, "inline": 0, "users": [], "started_at": time.time()}


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(data, indent=2))


def record_generation(user_id: int) -> None:
    data = _load()
    data["generated"] = data.get("generated", 0) + 1
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
    _save(data)


def record_decode(user_id: int) -> None:
    data = _load()
    data["decoded"] = data.get("decoded", 0) + 1
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
    _save(data)


def record_wifi(user_id: int) -> None:
    data = _load()
    data["wifi"] = data.get("wifi", 0) + 1
    _save(data)


def record_inline(user_id: int) -> None:
    data = _load()
    data["inline"] = data.get("inline", 0) + 1
    _save(data)


def get_stats() -> dict[str, Any]:
    return _load()
