"""Backups & snapshots.

These hold real recovery data, so cleanix **reports** them (with sizes and the
correct removal command) but never deletes them. The exception is backup-tool
*caches*, which are safe to clear.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX, MACOS
from cleanix.core.utils import home, iter_children, path_size, run_command, which


class BackupCacheCleaner(Cleaner):
    id = "backup_caches"
    name = "Backup-tool caches"
    description = "borg/restic/rclone caches (safe — not the repositories)"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        h = home()
        for path, label in (
            (h / ".cache" / "borg", "Borg cache"),
            (h / ".cache" / "restic", "restic cache"),
            (h / ".cache" / "rclone", "rclone cache"),
            (h / ".cache" / "deja-dup", "Déjà Dup cache"),
        ):
            if path.exists() and path_size(path) > 0:
                item = self.path_item(path, label)
                if item:
                    yield item


class SnapshotReporter(Cleaner):
    id = "snapshots"
    name = "Filesystem snapshots"
    description = "Timeshift/Snapper/btrfs snapshots (report only)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def find_items(self) -> Iterable[CleanableItem]:
        # Timeshift.
        for base in ("/timeshift/snapshots", "/run/timeshift/backup/timeshift-btrfs/snapshots"):
            root = Path(base)
            if root.is_dir():
                for snap in iter_children(root):
                    item = self.report_item(
                        snap, f"Timeshift snapshot: {snap.name}",
                        hint="remove with: timeshift --delete --snapshot '<name>'",
                    )
                    if item:
                        yield item

        # Snapper configs.
        if which("snapper"):
            code, out, _ = run_command(["snapper", "list-configs"], timeout=20)
            if code == 0:
                for line in out.splitlines()[2:]:
                    cfg = line.split("|")[0].strip()
                    if cfg:
                        snap_dir = Path("/.snapshots") if cfg == "root" else None
                        # Report the config; sizes are hard to attribute per-snap.
                        yield CleanableItem(
                            cleaner_id=self.id,
                            description=f"Snapper snapshots (config '{cfg}')",
                            size=path_size(snap_dir) if snap_dir else 0,
                            path=str(snap_dir) if snap_dir else "/.snapshots",
                            report_only=True,
                            requires_root=True,
                            hint=f"list/remove with: snapper -c {cfg} list / delete <N>",
                        )


class TimeMachineReporter(Cleaner):
    id = "time_machine"
    name = "Time Machine local snapshots"
    description = "APFS local Time Machine snapshots (report only)"
    requires_root = False
    platforms = (MACOS,)
    scope = SCOPE_SYSTEM

    def available(self):
        if not which("tmutil"):
            return "tmutil not found"
        return None

    def find_items(self) -> Iterable[CleanableItem]:
        code, out, _ = run_command(["tmutil", "listlocalsnapshots", "/"], timeout=20)
        if code != 0:
            return
        snaps = [ln.strip() for ln in out.splitlines() if "com.apple" in ln]
        if snaps:
            yield CleanableItem(
                cleaner_id=self.id,
                description=f"{len(snaps)} Time Machine local snapshot(s)",
                size=0,
                path="/",
                report_only=True,
                hint="thin with: tmutil thinlocalsnapshots / or deletelocalsnapshots <date>",
            )


class DeviceBackupReporter(Cleaner):
    id = "device_backups"
    name = "Mobile device backups"
    description = "iOS/Android device backups (report only — irreplaceable)"
    requires_root = False
    platforms = (MACOS,)

    def find_items(self) -> Iterable[CleanableItem]:
        base = home() / "Library" / "Application Support" / "MobileSync" / "Backup"
        if not base.is_dir():
            return
        for backup in iter_children(base):
            item = self.report_item(
                backup, f"iOS device backup: {backup.name}",
                hint="remove in Finder → Manage Backups, or delete this folder if intentional",
            )
            if item:
                yield item
