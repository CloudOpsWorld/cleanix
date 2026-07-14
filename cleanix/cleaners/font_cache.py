"""Fontconfig cache (``~/.cache/fontconfig``) — regenerated on demand."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import XDG_PLATFORMS
from cleanix.core.utils import cache_dir
from cleanix.core.utils import home, path_size


class FontCacheCleaner(Cleaner):
    id = "font_cache"
    name = "Font cache"
    description = "Fontconfig cache under ~/.cache/fontconfig"
    requires_root = False
    platforms = XDG_PLATFORMS

    def find_items(self) -> Iterable[CleanableItem]:
        cache = str(cache_dir())
        fc = Path(cache) / "fontconfig"
        if fc.exists() and path_size(fc) > 0:
            item = self.path_item(fc, "Fontconfig cache")
            if item:
                yield item
