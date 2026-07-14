"""pip's download/wheel cache (``~/.cache/pip``)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.utils import cache_dir
from cleanix.core.utils import home, path_size


class PipCacheCleaner(Cleaner):
    id = "pip_cache"
    name = "pip cache"
    description = "Cached wheels and downloads under ~/.cache/pip"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        cache = str(cache_dir())
        pip_dir = Path(cache) / "pip"
        if pip_dir.exists() and path_size(pip_dir) > 0:
            item = self.path_item(pip_dir, "pip download/wheel cache")
            if item:
                yield item
