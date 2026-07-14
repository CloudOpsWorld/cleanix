"""System coredumps under ``/var/lib/systemd/coredump``."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import iter_children, older_than


class CoredumpCleaner(Cleaner):
    id = "coredumps"
    scope = SCOPE_SYSTEM
    name = "Coredumps"
    description = "Crash coredumps kept by systemd-coredump"
    requires_root = True
    platforms = (LINUX,)

    def find_items(self) -> Iterable[CleanableItem]:
        root = Path("/var/lib/systemd/coredump")
        if not root.exists():
            return
        min_age = self.config.coredump_min_age_days
        for child in iter_children(root):
            if not older_than(child, min_age):
                continue
            item = self.path_item(child, f"Coredump: {child.name}")
            if item:
                yield item
