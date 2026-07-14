"""Pacman (Arch) — package cache, orphans, AUR helper build caches."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import home, path_size, run_command, which


class PacmanCleaner(Cleaner):
    id = "pacman"
    scope = SCOPE_SYSTEM
    name = "Pacman cache & orphans"
    description = "Cached tarballs, orphaned packages, and AUR build caches"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("pacman"):
            return "pacman not found (not an Arch-based system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        # 1) Package cache.
        cache = Path("/var/cache/pacman/pkg")
        size = path_size(cache) if cache.exists() else 0
        if size > 0:
            if which("paccache"):
                yield self.command_item(
                    ["paccache", "-r"],
                    "Trim cached packages, keeping the 3 latest versions",
                    size=size,
                )
            else:
                yield self.command_item(
                    ["pacman", "-Sc", "--noconfirm"],
                    "Remove cached packages for uninstalled software",
                    size=size,
                )

        # 2) Orphans — installed as deps, now required by nothing.
        code, out, _err = run_command(["pacman", "-Qtdq"], timeout=60)
        if code == 0 and out.strip():
            orphans = [ln.strip() for ln in out.splitlines() if ln.strip()]
            yield self.command_item(
                ["pacman", "-Rns", "--noconfirm", *orphans],
                f"Remove {len(orphans)} orphaned package(s)",
            )

        # 3) AUR helper build caches (user-owned).
        for rel, label in (
            (".cache/yay", "yay build cache"),
            (".cache/paru", "paru build cache"),
        ):
            item = self.path_item(
                home() / rel, label, requires_root=False
            )
            if item:
                yield item
