"""Leftovers from a broad set of desktop applications.

Focuses on app-specific logs, crash reports, temp and launcher caches that live
*outside* ~/.cache (which the generic cache cleaner already handles) — so there
is no double-coverage. User data (chat history, saves, documents) is untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import XDG_PLATFORMS
from cleanix.core.utils import home, iter_children, path_size

# (relative-to-home path, label) — logs / crash reports / temp / launcher caches.
_TARGETS: Tuple[Tuple[str, str], ...] = (
    # Gaming & launchers
    (".minecraft/logs", "Minecraft logs"),
    (".minecraft/crash-reports", "Minecraft crash reports"),
    (".local/share/PrismLauncher/logs", "PrismLauncher logs"),
    (".local/share/multimc/logs", "MultiMC logs"),
    (".local/share/Steam/logs", "Steam logs"),
    (".config/heroic/store_cache", "Heroic store cache"),
    (".local/share/lutris/coverart", "Lutris cover-art cache"),
    (".local/share/bottles/temp", "Bottles temp"),
    (".PlayOnLinux/tmp", "PlayOnLinux temp"),
    # Communication / meetings
    (".zoom/logs", "Zoom logs"),
    (".config/skypeforlinux/logs", "Skype logs"),
    (".config/Ferdium/logs", "Ferdium logs"),
    (".config/Rambox/logs", "Rambox logs"),
    # Media / creative
    (".config/obs-studio/logs", "OBS Studio logs"),
    (".config/obs-studio/crashes", "OBS Studio crash reports"),
    (".kodi/temp", "Kodi temp/logs"),
    # Cloud storage
    (".config/Nextcloud/logs", "Nextcloud logs"),
    (".dropbox/logs", "Dropbox logs"),
    (".config/insync/log", "Insync logs"),
    # Browser crash reports (caches live under ~/.cache, handled elsewhere)
    (".mozilla/firefox/Crash Reports", "Firefox crash reports"),
    (".thunderbird/Crash Reports", "Thunderbird crash reports"),
    (".config/google-chrome/Crash Reports", "Chrome crash reports"),
    # Virtualization app logs
    (".config/VirtualBox/VBoxSVC.log", "VirtualBox service log"),
    # Dev / misc
    (".expo", "Expo cache"),
    (".node-gyp", "node-gyp headers"),
)


class AppLeftoverCleaner(Cleaner):
    id = "app_leftovers"
    name = "Application leftovers"
    description = "Logs, crash reports and temp from many desktop apps"
    requires_root = False
    platforms = XDG_PLATFORMS

    def find_items(self) -> Iterable[CleanableItem]:
        h = home()
        for rel, label in _TARGETS:
            path = h / rel
            if path.exists() and path_size(path) > 0:
                item = self.path_item(path, label)
                if item:
                    yield item


class SnapAppCacheCleaner(Cleaner):
    id = "snap_app_cache"
    name = "Snap per-app caches"
    description = "Cache dirs inside ~/snap/*/{current,common}"
    requires_root = False
    platforms = XDG_PLATFORMS

    def find_items(self) -> Iterable[CleanableItem]:
        snap = home() / "snap"
        if not snap.is_dir():
            return
        for app in iter_children(snap):
            for rev in ("current", "common"):
                cache = app / rev / ".cache"
                if cache.is_dir() and path_size(cache) > 0:
                    item = self.path_item(cache, f"snap {app.name}/{rev}: cache")
                    if item:
                        yield item
