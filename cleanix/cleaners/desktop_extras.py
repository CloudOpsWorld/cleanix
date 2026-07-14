"""Rebuildable desktop search indexes and activity databases."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import XDG_PLATFORMS
from cleanix.core.utils import home, path_size


class SearchIndexCleaner(Cleaner):
    id = "search_index"
    name = "Desktop search indexes"
    description = "Baloo/Tracker/Zeitgeist indexes (rebuilt automatically)"
    requires_root = False
    platforms = XDG_PLATFORMS

    def _candidates(self) -> Iterable[Tuple[Path, str]]:
        h = home()
        data = h / ".local" / "share"
        cache = h / ".cache"
        yield data / "baloo", "KDE Baloo file index"
        yield cache / "tracker3", "GNOME Tracker cache"
        yield data / "tracker3", "GNOME Tracker index"
        yield cache / "tracker", "GNOME Tracker cache (v2)"
        yield data / "tracker", "GNOME Tracker index (v2)"
        yield data / "zeitgeist", "Zeitgeist activity log"
        yield data / "gvfs-metadata", "GVFS metadata"
        yield cache / "krunner", "KRunner cache"

    def find_items(self) -> Iterable[CleanableItem]:
        seen = set()
        for path, label in self._candidates():
            if path in seen or not path.exists() or path_size(path) <= 0:
                continue
            seen.add(path)
            item = self.path_item(path, label)
            if item:
                yield item
