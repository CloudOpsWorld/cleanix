"""Sandbox/universal package leftovers: Flatpak, Snap, Nix, AppImage.

These package formats each accumulate their own kind of cruft — unused runtimes,
superseded revisions, old generations — that the base package manager never
touches.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX, MACOS
from cleanix.core.utils import home, path_size, run_command, which


class FlatpakCleaner(Cleaner):
    id = "flatpak"
    scope = SCOPE_SYSTEM
    name = "Flatpak unused runtimes"
    description = "Runtimes/extensions no longer needed by any app"
    requires_root = False
    platforms = (LINUX,)

    def available(self):
        if not which("flatpak"):
            return "flatpak not found"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        code, out, _err = run_command(
            ["flatpak", "uninstall", "--unused", "--assumeno"], timeout=60
        )
        # The --assumeno dry run lists what *would* be removed.
        blob = f"{out}\n{_err}"
        refs = [
            ln.strip()
            for ln in blob.splitlines()
            if "/" in ln and ln.strip() and not ln.lower().startswith("proceed")
        ]
        # Fall back to offering the prune even if we couldn't parse counts.
        yield self.command_item(
            ["flatpak", "uninstall", "--unused", "-y"],
            f"Remove {len(refs)} unused Flatpak runtime(s)"
            if refs
            else "Remove unused Flatpak runtimes",
        )


class SnapCleaner(Cleaner):
    id = "snap"
    scope = SCOPE_SYSTEM
    name = "Snap old revisions"
    description = "Disabled superseded snap revisions still on disk"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("snap"):
            return "snap not found"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        code, out, _err = run_command(["snap", "list", "--all"], timeout=30)
        if code != 0 or not out.strip():
            return
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 6 and "disabled" in parts[5]:
                name, rev = parts[0], parts[2]
                yield self.command_item(
                    ["snap", "remove", name, "--revision", rev],
                    f"Remove disabled snap revision: {name} (rev {rev})",
                )


class NixGcCleaner(Cleaner):
    id = "nix_gc"
    scope = SCOPE_SYSTEM
    name = "Nix garbage collection"
    description = "Old profile generations and unreferenced Nix store paths"
    requires_root = False  # user store; multi-user setups may need root
    platforms = (LINUX, MACOS)

    def available(self):
        if not which("nix-collect-garbage") and not which("nix-store"):
            return "nix not found"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        # Estimate reclaimable space from dead store paths.
        size = 0
        code, out, _err = run_command(
            ["nix-store", "--gc", "--print-dead"], timeout=120
        )
        if code == 0 and out.strip():
            for p in out.splitlines():
                p = p.strip()
                if p:
                    size += path_size(p)
        yield self.command_item(
            ["nix-collect-garbage", "-d"],
            "Delete old generations and collect Nix garbage",
            size=size,
        )


class AppImageCruftCleaner(Cleaner):
    id = "appimage"
    name = "AppImage integration cruft"
    description = "Orphaned .desktop/icon entries from removed AppImages"
    requires_root = False
    platforms = (LINUX,)

    def find_items(self) -> Iterable[CleanableItem]:
        # appimaged writes launcher entries here; leftovers point nowhere.
        apps = home() / ".local" / "share" / "applications"
        if not apps.is_dir():
            return
        import os

        for entry in apps.glob("appimagekit_*.desktop"):
            try:
                text = entry.read_text(errors="ignore")
            except OSError:
                continue
            exec_line = next(
                (l for l in text.splitlines() if l.startswith("Exec=")), ""
            )
            m = re.search(r"Exec=\"?([^\s\"]+)", exec_line)
            target = m.group(1) if m else ""
            if target and not os.path.exists(os.path.expanduser(target)):
                item = self.path_item(
                    entry, f"Orphaned AppImage launcher: {entry.name}"
                )
                if item:
                    yield item
