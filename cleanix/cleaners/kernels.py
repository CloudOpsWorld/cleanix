"""Old-kernel removal.

Kernels pile up in ``/boot`` and ``/lib/modules`` and are a classic cause of a
full ``/boot``. This is inherently sensitive, so cleanix is conservative:

- Removal always goes through the **package manager**, which refuses to remove
  the running kernel and fixes up bootloader entries.
- The currently-running kernel (``uname -r``) is always excluded.
- The newest ``keep_kernels`` versions are always kept.
- Disabled entirely with ``remove_old_kernels: false``.
"""

from __future__ import annotations

import platform
import re
from typing import Iterable, List, Tuple

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import run_command, which


def _version_key(v: str) -> Tuple:
    """Best-effort natural sort key for a kernel version string."""
    parts = re.split(r"[.\-+~]", v)
    key = []
    for p in parts:
        key.append((0, int(p)) if p.isdigit() else (1, p))
    return tuple(key)


class OldKernelCleaner(Cleaner):
    id = "old_kernels"
    name = "Old kernels"
    description = "Superseded kernel packages (keeps running + newest N)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def available(self):
        if not self.config.remove_old_kernels:
            return "disabled in config (remove_old_kernels=false)"
        if not (which("dpkg") or which("rpm")):
            return "no supported package manager (dpkg/rpm) found"
        return None

    def _running(self) -> str:
        return platform.release()

    def _installed_debian(self) -> List[Tuple[str, str]]:
        """Return (package, version) for installed linux-image packages."""
        code, out, _ = run_command(
            ["dpkg-query", "-W", "-f=${Package} ${Version}\n", "linux-image-*"],
            timeout=30,
        )
        result = []
        if code == 0:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0].startswith("linux-image-"):
                    # skip meta-packages like linux-image-amd64
                    ver = parts[0][len("linux-image-"):]
                    if re.match(r"\d", ver):
                        result.append((parts[0], ver))
        return result

    def _installed_rpm(self) -> List[Tuple[str, str]]:
        code, out, _ = run_command(
            ["rpm", "-q", "kernel-core", "--qf", "%{VERSION}-%{RELEASE}.%{ARCH}\n"],
            timeout=30,
        )
        result = []
        if code == 0:
            for line in out.splitlines():
                line = line.strip()
                if line and not line.startswith("package "):
                    result.append((f"kernel-core-{line}", line))
        return result

    def find_items(self) -> Iterable[CleanableItem]:
        running = self._running()
        keep = max(self.config.keep_kernels, 1)

        if which("dpkg"):
            installed = self._installed_debian()
            purge_cmd = ["apt-get", "-y", "purge"]
        elif which("rpm"):
            installed = self._installed_rpm()
            purge_cmd = None  # handled below (dnf)
        else:
            return

        if len(installed) <= keep:
            return

        # Sort newest-first; always keep the newest `keep` and the running one.
        installed.sort(key=lambda pv: _version_key(pv[1]), reverse=True)
        keep_set = {pv[0] for pv in installed[:keep]}
        removable = [
            pv for pv in installed
            if pv[0] not in keep_set and running not in pv[1]
        ]
        if not removable:
            return

        for pkg, ver in removable:
            if which("dpkg"):
                cmd = ["apt-get", "-y", "purge", pkg]
            else:
                cmd = ["dnf", "-y", "remove", pkg]
            yield self.command_item(
                cmd, f"Remove old kernel {ver} ({pkg})"
            )
