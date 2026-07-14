"""Clean-run history and lifetime statistics."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

from cleanix.core.context import invoking_user


def _history_file() -> Path:
    return (
        invoking_user().home / ".local" / "state" / "cleanix" / "history.jsonl"
    )


def record(freed: int, items: int, *, mode: str) -> None:
    """Append a completed clean run to the history log. ``mode`` is one of
    'delete', 'quarantine'."""
    path = _history_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": time.time(), "freed": freed, "items": items, "mode": mode}
        with path.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # history is best-effort; never fail a clean over it


def load() -> List[Dict]:
    path = _history_file()
    if not path.exists():
        return []
    entries: List[Dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    except (OSError, ValueError):
        return entries
    return entries


def stats() -> Dict:
    entries = load()
    return {
        "runs": len(entries),
        "total_freed": sum(e.get("freed", 0) for e in entries),
        "total_items": sum(e.get("items", 0) for e in entries),
        "last_time": entries[-1]["time"] if entries else 0,
        "entries": entries,
    }
