"""IDE / code-editor leftovers.

Targets IDE-specific junk that the generic ~/.cache and Electron-cache cleaners
don't cover: VS Code-family logs/extension VSIX cache/stale workspace storage,
Sublime, Atom, Emacs native-comp cache, Zed logs, Android Studio, Qt Creator,
Godot, Unity. Installed extensions, settings and history are left alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import XDG_PLATFORMS
from cleanix.core.utils import config_dir, home, iter_children, older_than, path_size

# VS Code and its many forks all share the same layout under ~/.config/<App>/.
_VSCODE_APPS = (
    "Code", "Code - Insiders", "Code - OSS", "VSCodium", "Cursor", "Windsurf",
    "Positron", "Trae",
)


class IdeCleaner(Cleaner):
    id = "ide_caches"
    name = "IDE caches & logs"
    description = "VS Code/Sublime/Atom/Emacs/Zed/etc. logs and rebuildable caches"
    requires_root = False
    platforms = XDG_PLATFORMS

    def _vscode_items(self) -> Iterable[CleanableItem]:
        cfg = config_dir()
        for app in _VSCODE_APPS:
            base = cfg / app
            if not base.is_dir():
                continue
            for rel in ("logs", "CachedExtensionVSIXs", "CachedProfilesData",
                        "clp"):
                target = base / rel
                if target.is_dir() and path_size(target) > 0:
                    item = self.path_item(target, f"{app}: {rel}")
                    if item:
                        yield item
            # Stale per-workspace storage (rebuildable indexes/state).
            ws = base / "User" / "workspaceStorage"
            if ws.is_dir():
                for entry in iter_children(ws):
                    if older_than(entry, 30):
                        item = self.path_item(entry, f"{app}: stale workspace state")
                        if item:
                            yield item

    def _simple_dirs(self) -> Iterable[Tuple[Path, str]]:
        h = home()
        cfg = config_dir()
        # Sublime Text
        for st in ("sublime-text", "sublime-text-3"):
            yield cfg / st / "Cache", f"Sublime {st}: Cache"
            yield cfg / st / "Index", f"Sublime {st}: Index"
        # Atom (legacy)
        yield h / ".atom" / "compile-cache", "Atom compile cache"
        yield h / ".atom" / "blob-store", "Atom blob store"
        # Emacs native-compilation cache & autosaves
        yield h / ".emacs.d" / "eln-cache", "Emacs native-comp cache"
        yield h / ".emacs.d" / "auto-save-list", "Emacs autosave list"
        yield cfg / "emacs" / "eln-cache", "Emacs native-comp cache"
        # Zed logs
        yield h / ".local" / "share" / "zed" / "logs", "Zed logs"
        # Qt Creator
        yield h / ".local" / "share" / "QtProject" / "qtcreator" / "cache", "Qt Creator cache"
        # Godot logs & shader cache
        yield h / ".local" / "share" / "godot" / "app_userdata", "Godot logs/state"
        # Unity editor logs
        yield cfg / "unity3d" / "Editor.log", "Unity editor log"

    def find_items(self) -> Iterable[CleanableItem]:
        yield from self._vscode_items()
        seen = set()
        for path, label in self._simple_dirs():
            if path in seen or not path.exists() or path_size(path) <= 0:
                continue
            seen.add(path)
            item = self.path_item(path, label)
            if item:
                yield item
