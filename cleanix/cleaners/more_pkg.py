"""Cleanup steps for the remaining package managers.

Rounds out coverage across the ecosystem: Conda/Mamba, Guix, Solus eopkg,
Clear Linux swupd, OCaml opam, SDKMAN!, RubyGems, and cpanm — each invoking its
native cleanup, or clearing its download/cache dirs where there is no command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import home, path_size, which


class CondaCleaner(Cleaner):
    id = "conda"
    name = "Conda/Mamba caches"
    description = "Unused packages, tarballs and index cache (conda clean -a)"
    requires_root = False

    def _pkg_dirs(self):
        h = home()
        for base in ("miniconda3", "anaconda3", "miniforge3", "mambaforge", ".conda"):
            yield h / base / "pkgs"

    def available(self):
        if which("conda") or which("mamba") or which("micromamba"):
            return None
        if any(p.exists() for p in self._pkg_dirs()):
            return None
        return "conda/mamba not found"

    def find_items(self) -> Iterable[CleanableItem]:
        size = sum(path_size(p) for p in self._pkg_dirs() if p.exists())
        binary = "mamba" if which("mamba") else "conda"
        if which(binary) or which("micromamba"):
            tool = binary if which(binary) else "micromamba"
            yield self.command_item(
                [tool, "clean", "-a", "-y"],
                "Remove unused conda packages, tarballs and index cache",
                size=size,
            )


class GuixCleaner(Cleaner):
    id = "guix"
    name = "Guix garbage collection"
    description = "Unreferenced store items and old generations (guix gc)"
    requires_root = False
    platforms = (LINUX,)

    def available(self):
        return None if which("guix") else "guix not found"

    def find_items(self) -> Iterable[CleanableItem]:
        yield self.command_item(
            ["guix", "gc", "-C"],
            "Collect Guix garbage (unreferenced store items)",
        )


class EopkgCleaner(Cleaner):
    id = "eopkg"
    name = "Solus eopkg (cache & orphans)"
    description = "Cached packages and orphaned dependencies"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def available(self):
        return None if which("eopkg") else "eopkg not found (not a Solus system)"

    def find_items(self) -> Iterable[CleanableItem]:
        cache = Path("/var/cache/eopkg/packages")
        size = path_size(cache) if cache.exists() else 0
        yield self.command_item(
            ["eopkg", "delete-cache"], "Clear the eopkg package cache", size=size
        )
        yield self.command_item(
            ["eopkg", "remove-orphans", "-y"], "Remove orphaned dependencies"
        )


class SwupdCleaner(Cleaner):
    id = "swupd"
    name = "Clear Linux swupd cache"
    description = "Cached update bundles (swupd clean)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def available(self):
        return None if which("swupd") else "swupd not found (not a Clear Linux system)"

    def find_items(self) -> Iterable[CleanableItem]:
        cache = Path("/var/lib/swupd")
        size = path_size(cache) if cache.exists() else 0
        yield self.command_item(
            ["swupd", "clean", "--all"], "Clean the swupd cache", size=size
        )


class OpamCleaner(Cleaner):
    id = "opam"
    name = "OPAM cache (OCaml)"
    description = "Cached downloads and build logs (opam clean)"
    requires_root = False

    def available(self):
        return None if which("opam") else "opam not found"

    def find_items(self) -> Iterable[CleanableItem]:
        size = path_size(home() / ".opam" / "download-cache")
        yield self.command_item(
            ["opam", "clean", "-y"],
            "Clear opam download cache and build logs",
            size=size,
        )


class SdkmanCleaner(Cleaner):
    id = "sdkman"
    name = "SDKMAN! archives"
    description = "Downloaded SDK archives and temp files"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        base = home() / ".sdkman"
        for sub in ("archives", "tmp"):
            target = base / sub
            if target.is_dir() and path_size(target) > 0:
                item = self.path_item(target, f"SDKMAN! {sub}")
                if item:
                    yield item


class GemCleanupCleaner(Cleaner):
    id = "gem"
    name = "RubyGems old versions"
    description = "Remove superseded installed gem versions (gem cleanup)"
    requires_root = False

    def available(self):
        return None if which("gem") else "gem not found"

    def find_items(self) -> Iterable[CleanableItem]:
        yield self.command_item(
            ["gem", "cleanup"],
            "Remove old versions of installed gems",
        )


class CpanmCleaner(Cleaner):
    id = "cpanm"
    name = "cpanm build leftovers"
    description = "Perl cpanminus work/build directories"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        work = home() / ".cpanm" / "work"
        if work.is_dir() and path_size(work) > 0:
            item = self.path_item(work, "cpanm work directory")
            if item:
                yield item
