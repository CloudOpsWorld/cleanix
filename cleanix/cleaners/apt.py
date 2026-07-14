"""APT (Debian/Ubuntu) — package cache, orphaned deps, residual configs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import path_size, run_command, which


class AptCleaner(Cleaner):
    id = "apt"
    scope = SCOPE_SYSTEM
    name = "APT cache & orphans"
    description = "Downloaded .deb archives, orphaned deps, residual configs"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("apt-get") or not which("dpkg"):
            return "apt-get/dpkg not found (not a Debian/Ubuntu system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        # 1) Downloaded .deb archives.
        archives = Path("/var/cache/apt/archives")
        cached = sum(path_size(deb) for deb in archives.glob("*.deb")) if archives.exists() else 0
        if cached > 0:
            yield self.command_item(
                ["apt-get", "clean"],
                "Remove downloaded .deb package archives",
                size=cached,
            )

        # 2) Orphaned dependencies (autoremovable).
        code, out, _err = run_command(["apt-get", "-s", "autoremove"], timeout=60)
        if code == 0 and out:
            removals = [ln for ln in out.splitlines() if ln.startswith("Remv ")]
            if removals:
                yield self.command_item(
                    ["apt-get", "-y", "autoremove", "--purge"],
                    f"Autoremove {len(removals)} orphaned package(s)",
                )

        # 3) Residual configs — packages removed but not purged (dpkg "rc").
        code, out, _err = run_command(["dpkg", "-l"], timeout=60)
        if code == 0 and out:
            rc = [
                ln.split()[1]
                for ln in out.splitlines()
                if ln.startswith("rc ") and len(ln.split()) > 1
            ]
            if rc:
                yield self.command_item(
                    ["apt-get", "-y", "purge", *rc],
                    f"Purge {len(rc)} leftover package config(s) (dpkg 'rc' state)",
                )

        # 4) deborphan — libraries no longer required by anything.
        if which("deborphan"):
            code, out, _err = run_command(["deborphan"], timeout=60)
            if code == 0 and out.strip():
                orphans = [ln.strip() for ln in out.splitlines() if ln.strip()]
                yield self.command_item(
                    ["apt-get", "-y", "purge", *orphans],
                    f"Purge {len(orphans)} orphaned librar(y/ies) (deborphan)",
                )
