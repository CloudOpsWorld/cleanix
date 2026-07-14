"""``.DS_Store`` and AppleDouble (``._*``) litter.

macOS scatters ``.DS_Store`` directory-metadata files and ``._name``
AppleDouble resource-fork files across any filesystem it touches — including
network shares and USB drives that later get read on Linux/BSD. They are pure
metadata and safe to delete anywhere. Runs on every platform for that reason.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.utils import home, walk_pruned


class AppleLitterCleaner(Cleaner):
    id = "apple_litter"
    name = ".DS_Store / AppleDouble"
    description = "macOS .DS_Store and ._* metadata litter in your home tree"
    requires_root = False

    def available(self):
        if not self.config.remove_apple_litter:
            return "disabled in config (remove_apple_litter=false)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        root = home()
        for dirpath, _dirs, files in walk_pruned(root):
            for name in files:
                if name == ".DS_Store" or (
                    name.startswith("._") and len(name) > 2
                ):
                    p = os.path.join(dirpath, name)
                    item = self.path_item(p, f"Apple litter: {p}")
                    if item:
                        yield item
