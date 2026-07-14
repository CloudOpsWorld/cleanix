"""VM / container / cloud-CLI leftovers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from cleanix.cleaners.base import Cleaner, SCOPE_SYSTEM
from cleanix.core.models import CleanableItem
from cleanix.core.platform import LINUX
from cleanix.core.utils import home, iter_children, path_size


class VmToolingCleaner(Cleaner):
    id = "vm_tooling"
    name = "VM & cloud tooling caches"
    description = "VirtualBox logs, Vagrant boxes, k8s & cloud-CLI caches"
    requires_root = False

    def find_items(self) -> Iterable[CleanableItem]:
        h = home()

        # VirtualBox per-VM logs.
        vbox = h / "VirtualBox VMs"
        if vbox.is_dir():
            for vm in iter_children(vbox):
                logs = vm / "Logs"
                if logs.is_dir() and path_size(logs) > 0:
                    item = self.path_item(logs, f"VirtualBox logs: {vm.name}")
                    if item:
                        yield item

        # Simple regenerable caches.
        simple: Iterable[Tuple[Path, str]] = (
            (h / ".vagrant.d" / "tmp", "Vagrant temp"),
            (h / ".vagrant.d" / "boxes", "Vagrant downloaded boxes"),
            (h / ".kube" / "cache", "kubectl cache"),
            (h / ".kube" / "http-cache", "kubectl HTTP cache"),
            (h / ".minikube" / "cache", "minikube cache"),
            (h / ".cache" / "helm", "Helm cache"),
            (h / ".aws" / "cli" / "cache", "AWS CLI cache"),
            (h / ".azure" / "logs", "Azure CLI logs"),
            (h / ".config" / "gcloud" / "logs", "gcloud logs"),
            (h / ".terraform.d" / "plugin-cache", "Terraform plugin cache"),
            (h / ".cache" / "pulumi", "Pulumi cache"),
        )
        seen = set()
        for path, label in simple:
            if path in seen or not path.exists() or path_size(path) <= 0:
                continue
            seen.add(path)
            item = self.path_item(path, label)
            if item:
                yield item


class LibvirtSaveReporter(Cleaner):
    id = "libvirt_saves"
    name = "libvirt saved VM states"
    description = "Suspended-VM memory images (report only — real state)"
    requires_root = True
    platforms = (LINUX,)
    scope = SCOPE_SYSTEM

    def find_items(self) -> Iterable[CleanableItem]:
        save = Path("/var/lib/libvirt/qemu/save")
        if not save.is_dir():
            return
        for child in iter_children(save):
            item = self.report_item(
                child,
                f"libvirt saved state: {child.name}",
                hint="restore/discard with: virsh restore / virsh managedsave-remove <vm>",
            )
            if item:
                yield item
