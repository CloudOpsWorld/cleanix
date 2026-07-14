"""localepurge-style removal of unused locale & man-page translations.

Off by default (``purge_unused_locales``): it frees space but removes UI
translations and translated manuals for languages you don't use. We keep the
system's configured language(s), plus English and the C/POSIX locale.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Set

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import iter_children


class LocalePurgeCleaner(Cleaner):
    id = "localepurge"
    name = "Unused localizations"
    description = "Locale & man-page translations for unused languages (opt-in)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def available(self):
        if not self.config.purge_unused_locales:
            return "disabled in config (purge_unused_locales=false)"
        return None

    def _keep_languages(self) -> Set[str]:
        keep = {"en", "en_US", "en_GB", "C", "POSIX"}
        for var in ("LANG", "LC_ALL", "LANGUAGE", "LC_MESSAGES"):
            val = os.environ.get(var, "")
            for part in val.replace(":", " ").split():
                code = part.split(".")[0].split("_")[0]
                if code:
                    keep.add(code)
                    keep.add(part.split(".")[0])
        return keep

    def _wanted(self, name: str, keep: Set[str]) -> bool:
        base = name.split(".")[0]
        return base in keep or base.split("_")[0] in keep

    def find_items(self) -> Iterable[CleanableItem]:
        keep = self._keep_languages()

        locale_root = Path("/usr/share/locale")
        if locale_root.is_dir():
            for child in iter_children(locale_root):
                if child.is_dir() and not self._wanted(child.name, keep):
                    item = self.path_item(child, f"Locale: {child.name}")
                    if item:
                        yield item

        man_root = Path("/usr/share/man")
        if man_root.is_dir():
            for child in iter_children(man_root):
                # man pages sit in man/<lang>/; man/man1 etc. are English.
                if (
                    child.is_dir()
                    and not child.name.startswith("man")
                    and not self._wanted(child.name, keep)
                ):
                    item = self.path_item(child, f"Man pages: {child.name}")
                    if item:
                        yield item
