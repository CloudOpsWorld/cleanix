"""Freedesktop trash (``~/.local/share/Trash``) and per-mount trashes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import XDG_PLATFORMS
from cleanix.core.utils import data_dir, current_uid
from cleanix.core.utils import home, iter_children


class TrashCleaner(Cleaner):
    id = "trash"
    name = "Trash"
    description = "Files sitting in the desktop trash/recycle bin"
    requires_root = False
    platforms = XDG_PLATFORMS

    def _trash_dirs(self) -> Iterable[Path]:
        data = str(data_dir())
        yield Path(data) / "Trash"
        # Per-mount trash dirs, e.g. /media/usb/.Trash-1000
        uid = current_uid() or 1000
        for mount_root in ("/media", "/mnt", "/run/media"):
            base = Path(mount_root)
            if not base.exists():
                continue
            for child in iter_children(base):
                cand = child / f".Trash-{uid}"
                if cand.exists():
                    yield cand

    def find_items(self) -> Iterable[CleanableItem]:
        for trash in self._trash_dirs():
            # Only clear the contents subdirs, never the Trash dir itself.
            for sub in ("files", "info", "expunged"):
                target = trash / sub
                for child in iter_children(target):
                    item = self.path_item(
                        child, f"Trash: {child.name}"
                    )
                    if item:
                        yield item
