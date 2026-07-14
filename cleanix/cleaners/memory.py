"""Safe memory reclamation (RAM caches + swap).

These operations NEVER kill or trim running applications — they only ask the
kernel to release *clean, reclaimable* memory:

- **drop_caches** frees the page/dentry/inode cache. The kernel simply re-reads
  from disk later; no process loses data (we ``sync`` first to flush dirty pages).
- **swap reclaim** (``swapoff -a && swapon -a``) pulls swapped pages back into
  RAM, emptying swap — but only when there is clearly enough free RAM to hold
  them, so it can never trigger an out-of-memory kill.

They are opt-in (``default_enabled = False``): run explicitly with
``cleanix clean --only memory,swap``. All are read-only until you execute.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from cleanix.cleaners.base import SCOPE_SYSTEM, Cleaner
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX, MACOS
from cleanix.core.utils import which


def _meminfo() -> Dict[str, int]:
    """Parse /proc/meminfo into a dict of bytes (values are in kB there)."""
    info: Dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            parts = rest.split()
            if parts and parts[0].isdigit():
                info[key.strip()] = int(parts[0]) * 1024
    except OSError:
        pass
    return info


class DropCachesCleaner(Cleaner):
    id = "memory"
    name = "RAM cache (drop_caches)"
    description = "Free reclaimable page/dentry/inode cache (safe; no app impact)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM
    default_enabled = False

    def find_items(self) -> Iterable[CleanableItem]:
        info = _meminfo()
        reclaimable = info.get("Cached", 0) + info.get("Buffers", 0) + info.get(
            "SReclaimable", 0
        )
        if reclaimable <= 0:
            return
        # `sync` flushes dirty pages so nothing is lost; then drop clean caches.
        yield self.command_item(
            ["sh", "-c", "sync && echo 3 > /proc/sys/vm/drop_caches"],
            "Drop reclaimable RAM caches (page/dentry/inode)",
            size=reclaimable,
        )


class SwapReclaimCleaner(Cleaner):
    id = "swap"
    name = "Swap reclaim"
    description = "Move swapped pages back to RAM to empty swap (OOM-guarded)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM
    default_enabled = False

    def find_items(self) -> Iterable[CleanableItem]:
        info = _meminfo()
        swap_total = info.get("SwapTotal", 0)
        swap_free = info.get("SwapFree", 0)
        swap_used = swap_total - swap_free
        available = info.get("MemAvailable", 0)

        if swap_used <= 0:
            return
        # Only offer if free RAM comfortably exceeds swap in use (20% headroom),
        # otherwise swapoff could fail or force an OOM — never risk that.
        if available < swap_used * 1.2:
            return
        yield self.command_item(
            ["sh", "-c", "swapoff -a && swapon -a"],
            f"Reclaim swap (~{swap_used // (1024 * 1024)} MiB) back into free RAM",
            size=swap_used,
        )


class MacMemoryPurgeCleaner(Cleaner):
    id = "memory_macos"
    name = "macOS memory purge"
    description = "Free inactive memory with Apple's supported `purge` tool"
    requires_root = True
    platforms = (MACOS,)
    scope = SCOPE_SYSTEM
    default_enabled = False

    def available(self):
        return None if which("purge") else "purge not found"

    def find_items(self) -> Iterable[CleanableItem]:
        yield self.command_item(
            ["purge"],
            "Purge inactive memory (disk cache) — Apple-supported, safe",
        )
