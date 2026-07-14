"""Editor swap/undo files, build litter, loose core dumps, backup files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.utils import home, iter_children, older_than, path_size, walk_pruned


class EditorStateCleaner(Cleaner):
    id = "editor_state"
    name = "Editor swap/undo state"
    description = "Vim/Neovim swap, undo and backup state (rebuildable)"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        h = home()
        for base in (
            h / ".local" / "state" / "nvim",
            h / ".local" / "share" / "nvim",
            h / ".vim",
            h / ".config" / "nvim",
        ):
            for sub in ("swap", "undo", "backup"):
                target = base / sub
                if target.is_dir():
                    for child in iter_children(target):
                        # A .swp for an open buffer is recent; leave it be.
                        if older_than(child, 1):
                            item = self.path_item(child, f"Editor {sub}: {child.name}")
                            if item:
                                yield item


class BuildLitterCleaner(Cleaner):
    id = "build_litter"
    name = "Build & test litter"
    description = "__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .tox"
    requires_root = False

    _DIRS = {
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".tox", ".hypothesis", ".ipynb_checkpoints",
    }

    def find_items(self) -> Iterable[CleanableItem]:
        root = home()
        for dirpath, dirs, _files in walk_pruned(root):
            for d in list(dirs):
                if d in self._DIRS:
                    p = os.path.join(dirpath, d)
                    item = self.path_item(p, f"Build litter: {p}")
                    if item:
                        yield item
                    # Don't descend into what we've already offered.
                    dirs.remove(d)


class HomeCoreDumpCleaner(Cleaner):
    id = "home_coredumps"
    name = "Loose core dumps"
    description = "core / core.<pid> crash dumps left in the home tree"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        root = home()
        for dirpath, _dirs, files in walk_pruned(root):
            for name in files:
                if name == "core" or name.startswith("core."):
                    p = Path(dirpath, name)
                    try:
                        if not p.is_file() or p.is_symlink():
                            continue
                    except OSError:
                        continue
                    # A real core dump is large and binary; skip tiny files
                    # named "core" that are probably source (e.g. "core.py"→no,
                    # startswith core. would match core.py; require no dot-ext).
                    if "." in name and not name.split(".", 1)[1].isdigit():
                        continue
                    if path_size(p) < 4096:
                        continue
                    item = self.path_item(p, f"Core dump: {p}")
                    if item:
                        yield item


class BackupFileCleaner(Cleaner):
    id = "backup_files"
    name = "Editor backup files"
    description = "*~, *.orig, *.bak, *.rej litter (opt-in)"
    requires_root = False

    _SUFFIXES = (".orig", ".bak", ".rej")

    def available(self):
        if not self.config.remove_backup_files:
            return "disabled in config (remove_backup_files=false)"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        root = home()
        for dirpath, _dirs, files in walk_pruned(root):
            for name in files:
                if name.endswith("~") or name.endswith(self._SUFFIXES):
                    p = Path(dirpath, name)
                    if p.is_symlink() or not p.is_file():
                        continue
                    item = self.path_item(p, f"Backup file: {p}")
                    if item:
                        yield item
