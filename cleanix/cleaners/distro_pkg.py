"""Package-manager cleaners for the less-common Linux distros.

openSUSE (zypper), Alpine (apk), Void (xbps), and Gentoo (portage). Each offers
cache cleanup and, where cheaply detectable, orphan removal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import path_size, run_command, which


class ZypperCleaner(Cleaner):
    id = "zypper"
    scope = SCOPE_SYSTEM
    name = "Zypper cache (openSUSE)"
    description = "Cached RPMs and metadata under /var/cache/zypp"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("zypper"):
            return "zypper not found (not an openSUSE system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        cache = Path("/var/cache/zypp")
        size = path_size(cache) if cache.exists() else 0
        if size > 0:
            yield self.command_item(
                ["zypper", "clean", "--all"],
                "Clean all zypper caches (packages + metadata)",
                size=size,
            )


class ApkCleaner(Cleaner):
    id = "apk"
    scope = SCOPE_SYSTEM
    name = "apk cache (Alpine)"
    description = "Cached packages under /var/cache/apk"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("apk"):
            return "apk not found (not an Alpine system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        cache = Path("/var/cache/apk")
        size = path_size(cache) if cache.exists() else 0
        if size > 0:
            yield self.command_item(
                ["apk", "cache", "clean", "-v"],
                "Remove obsolete cached apk packages",
                size=size,
            )


class XbpsCleaner(Cleaner):
    id = "xbps"
    scope = SCOPE_SYSTEM
    name = "XBPS cache & orphans (Void)"
    description = "Cached packages and orphaned dependencies"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("xbps-remove"):
            return "xbps not found (not a Void system)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        cache = Path("/var/cache/xbps")
        size = path_size(cache) if cache.exists() else 0
        if size > 0:
            yield self.command_item(
                ["xbps-remove", "-Oy"],
                "Clean obsolete packages from the XBPS cache",
                size=size,
            )
        # Orphaned packages.
        code, out, _err = run_command(["xbps-query", "-O"], timeout=45)
        if code == 0 and out.strip():
            yield self.command_item(
                ["xbps-remove", "-oy"],
                "Remove orphaned packages",
            )


class PortageCleaner(Cleaner):
    id = "portage"
    scope = SCOPE_SYSTEM
    name = "Portage distfiles (Gentoo)"
    description = "Stale source tarballs and binary packages"
    requires_root = True
    platforms = (LINUX,)

    def available(self):
        if not which("emerge"):
            return "emerge not found (not a Gentoo system)"
        if not which("eclean") and not which("eclean-dist"):
            return "eclean not found (install app-portage/gentoolkit)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        distfiles = 0
        for base in ("/var/cache/distfiles", "/usr/portage/distfiles"):
            p = Path(base)
            if p.exists():
                distfiles += path_size(p)

        dist_cmd = ["eclean-dist", "-d"] if which("eclean-dist") else ["eclean", "-d", "distfiles"]
        yield self.command_item(
            dist_cmd, "Clean obsolete source distfiles", size=distfiles
        )

        pkg_cmd = ["eclean-pkg", "-d"] if which("eclean-pkg") else ["eclean", "-d", "packages"]
        yield self.command_item(
            pkg_cmd, "Clean obsolete binary packages"
        )
