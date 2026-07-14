"""Container-engine leftovers (Docker / Podman).

Dangling images, stopped containers, unused networks and build cache pile up
fast. We estimate the reclaimable amount from ``system df`` and offer a
``system prune``. Volumes are only included when explicitly enabled, since they
can hold real data.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, List, Optional

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.utils import run_command, which

_SIZE_RE = re.compile(r"([\d.]+)\s*([KMGT]?B)", re.IGNORECASE)
_UNIT = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}


def _parse_size(text: str) -> int:
    m = _SIZE_RE.search(text or "")
    if not m:
        return 0
    value = float(m.group(1))
    unit = m.group(2).upper()
    return int(value * _UNIT.get(unit, 1))


class _ContainerCleaner(Cleaner):
    binary = ""
    requires_root = False

    def available(self):
        if not which(self.binary):
            return f"{self.binary} not found"
        return None

    def _reclaimable(self) -> int:
        code, out, _err = run_command(
            [self.binary, "system", "df", "--format", "{{json .}}"], timeout=30
        )
        if code != 0 or not out.strip():
            return 0
        total = 0
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += _parse_size(row.get("Reclaimable", ""))
        return total

    def find_items(self) -> Iterable[CleanableItem]:
        reclaimable = self._reclaimable()
        cmd: List[str] = [self.binary, "system", "prune", "-f"]
        desc = "Prune stopped containers, dangling images, networks, build cache"
        if self.config.docker_prune_volumes:
            cmd.append("--volumes")
            desc += " (incl. unused volumes)"
        yield self.command_item(cmd, desc, size=reclaimable)


class DockerCleaner(_ContainerCleaner):
    id = "docker"
    scope = SCOPE_SYSTEM
    name = "Docker leftovers"
    description = "Dangling images, stopped containers, build cache"
    binary = "docker"


class PodmanCleaner(_ContainerCleaner):
    id = "podman"
    scope = SCOPE_SYSTEM
    name = "Podman leftovers"
    description = "Dangling images, stopped containers, build cache"
    binary = "podman"
