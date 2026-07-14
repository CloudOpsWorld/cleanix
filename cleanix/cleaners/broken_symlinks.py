"""Dangling (broken) symlinks — a classic leftover from removed software.

When a package or manually-installed tool is deleted, symlinks pointing into it
(in ``~/.local/bin``, ``/usr/local/bin``, menu entries, ...) are frequently left
behind pointing at nothing. These are always safe to remove.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.utils import expand
from cleanix.core.utils import home, is_broken_symlink, iter_children


class BrokenSymlinkCleaner(Cleaner):
    id = "broken_symlinks"
    name = "Broken symlinks"
    description = "Dangling symlinks left behind by uninstalled software"
    requires_root = False  # per-item; system paths flagged individually

    def find_items(self) -> Iterable[CleanableItem]:
        home_str = str(home())
        seen = set()
        for raw in self.config.symlink_scan_dirs:
            base = expand(raw)
            if not base.is_dir():
                continue
            for child in iter_children(base):
                key = str(child)
                if key in seen:
                    continue
                seen.add(key)
                if not is_broken_symlink(child):
                    continue
                try:
                    target = os.readlink(child)
                except OSError:
                    target = "?"
                needs_root = not key.startswith(home_str)
                yield CleanableItem(
                    cleaner_id=self.id,
                    description=f"Broken symlink: {child} -> {target}",
                    size=0,
                    path=str(child),
                    requires_root=needs_root,
                )
