"""DNF/YUM (Fedora/RHEL) — cache and orphaned packages."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import path_size, run_command, which


class DnfCleaner(Cleaner):
    id = "dnf"
    scope = SCOPE_SYSTEM
    name = "DNF cache & orphans"
    description = "Cached metadata/RPMs and packages left over as unneeded deps"
    requires_root = True
    platforms = (LINUX,)

    def _binary(self) -> str:
        if which("dnf5"):
            return "dnf5"
        if which("dnf"):
            return "dnf"
        return "yum"  # older RHEL/CentOS fallback

    def available(self):
        if not (which("dnf") or which("dnf5") or which("yum")):
            return "dnf/yum not found (not a Fedora/RHEL system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        binary = self._binary()

        cache = Path("/var/cache/dnf")
        size = path_size(cache) if cache.exists() else 0
        if size > 0:
            yield self.command_item(
                [binary, "clean", "all"],
                "Clean all DNF caches (metadata + packages)",
                size=size,
            )

        # Orphaned packages (installed as deps, no longer required).
        code, out, _err = run_command(
            [binary, "repoquery", "--unneeded", "--quiet"], timeout=90
        )
        if code == 0 and out.strip():
            pkgs = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if pkgs:
                yield self.command_item(
                    [binary, "-y", "autoremove"],
                    f"Autoremove {len(pkgs)} orphaned package(s)",
                )
