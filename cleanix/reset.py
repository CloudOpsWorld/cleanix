"""Factory-reset advisor.

There is no single "factory reset" across the *nix world, and on most systems it
is irreversible. So cleanix does not *perform* a reset — it detects your system's
reset capability and produces a **tiered, copy-pasteable plan**, loudest about
the safeguards. Declarative/image-based systems (NixOS, rpm-ostree, Guix,
MicroOS) have a genuine, reversible factory reset; traditional distros do not,
and the plan says so honestly.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Tuple

from cleanix.core.platform import MACOS, current_distro, current_os
from cleanix.core.utils import which


@dataclass
class ResetAction:
    """A reversible reset command cleanix is allowed to *execute*."""

    description: str
    command: List[str]
    requires_root: bool = True
    undo: str = ""


@dataclass
class Tier:
    key: str            # user | packages | system
    title: str
    warning: str
    steps: List[str] = field(default_factory=list)


@dataclass
class ResetPlan:
    strategy: str
    reversible: bool
    summary: str
    prerequisites: List[str] = field(default_factory=list)
    tiers: List[Tier] = field(default_factory=list)
    # Only populated for reversible strategies; these are the ONLY commands
    # cleanix will run for --execute. Irreversible steps stay advisory-only.
    actions: List[ResetAction] = field(default_factory=list)


def confirmation_phrase() -> str:
    """The exact phrase a user must type to authorize execution."""
    try:
        host = socket.gethostname() or "this-system"
    except Exception:  # noqa: BLE001
        host = "this-system"
    return f"reset {host}"


def execute_actions(
    plan: ResetPlan, runner: Callable[[List[str]], int]
) -> List[Tuple[ResetAction, int]]:
    """Run the plan's reversible actions in order, stopping on first failure.

    ``runner`` executes an argv and returns a process exit code; injecting it
    keeps this testable and keeps subprocess concerns in the CLI layer.
    """
    results: List[Tuple[ResetAction, int]] = []
    for action in plan.actions:
        code = runner(action.command)
        results.append((action, code))
        if code != 0:
            break
    return results


def _detect_strategy() -> str:
    if current_os() == MACOS:
        return "macos"
    if Path("/etc/NIXOS").exists() or current_distro() == "nixos":
        return "nixos"
    if Path("/run/ostree-booted").exists() or which("rpm-ostree"):
        return "ostree"
    if which("transactional-update"):
        return "microos"
    if which("guix") and Path("/run/current-system").exists():
        return "guix"
    return "traditional"


# --- per-strategy tier builders ---------------------------------------------
def _user_tier(distro_hint: str = "") -> Tier:
    return Tier(
        key="user",
        title="User environment reset (per account)",
        warning="Removes desktop/app settings, extensions, keyrings and caches. "
        "Documents/Downloads/Pictures are preserved. Not reversible without the backup.",
        steps=[
            "Back up first:  tar czf ~/dotfiles-backup.tgz -C $HOME .config .local .cache .mozilla .gnupg .ssh",
            "Preview what cleanix would remove:  cleanix clean --current-user",
            "Then reset the shell/app state to defaults, e.g.:",
            "  rm -rf ~/.config ~/.local/share ~/.cache ~/.local/state",
            "  (keep ~/.ssh, ~/.gnupg unless you truly want new keys)",
            "Log out and back in — the DE recreates default settings.",
        ],
    )


def build_plan(scope: str) -> ResetPlan:
    strategy = _detect_strategy()
    common_prereq = [
        "Take a full snapshot/backup you can boot from (Timeshift, btrfs/ZFS "
        "snapshot, or a full image). cleanix will not do this for you.",
        "Close all apps and save your work; a reset cannot be undone mid-way.",
    ]

    if strategy == "nixos":
        plan = ResetPlan(
            strategy="NixOS (declarative)",
            reversible=True,
            summary="NixOS is fully declarative: the system is rebuilt from "
            "configuration.nix, and every rebuild is a bootable generation. A "
            "true, reversible factory reset.",
            prerequisites=common_prereq,
            tiers=[
                _user_tier(),
                Tier(
                    "packages",
                    "Package/system state reset",
                    "Reverts the system to a pristine configuration and drops all "
                    "extra generations.",
                    [
                        "Restore a minimal/original configuration.nix (or generation 1).",
                        "sudo nixos-rebuild switch        # rebuild from that config",
                        "sudo nix-collect-garbage -d      # delete old generations",
                        "sudo nixos-rebuild boot --rollback  # or pick generation 1 in the boot menu",
                    ],
                ),
                Tier(
                    "system",
                    "Deep reset",
                    "Wipes mutable state not tracked by Nix.",
                    [
                        "Remove /home/<user> state (see user tier) for a like-new account.",
                        "Optionally re-run the installer for a bit-for-bit factory image.",
                    ],
                ),
            ],
            actions=[
                ResetAction(
                    "Roll back to the previous NixOS generation",
                    ["nixos-rebuild", "switch", "--rollback"],
                    requires_root=True,
                    undo="pick a newer generation at boot, or run nixos-rebuild switch",
                ),
            ],
        )
        return _filter(plan, scope)

    if strategy == "ostree":
        return _filter(ResetPlan(
            strategy="rpm-ostree / OSTree image-based (Silverblue, Kinoite, IoT)",
            reversible=True,
            summary="The base OS is an immutable image; your changes are layers "
            "and overrides on top. Resetting the layers gives a genuine, "
            "reversible factory image.",
            prerequisites=common_prereq,
            tiers=[
                _user_tier(),
                Tier("packages", "Drop layered packages & overrides",
                     "Returns the OS layer to the pristine base image.",
                     [
                         "rpm-ostree reset          # remove all layered pkgs + overrides",
                         "rpm-ostree rollback        # or return to the previous deployment",
                         "flatpak uninstall --all    # optional: remove all Flatpak apps",
                     ]),
                Tier("system", "Reset /etc & redeploy",
                     "OSTree 3-way merges /etc; review and discard local changes.",
                     [
                         "ostree admin config-diff   # see your /etc changes vs base",
                         "Revert unwanted /etc edits, then reboot into the clean deployment.",
                     ]),
            ],
            actions=[
                ResetAction(
                    "Remove all layered packages and overrides (reset to base image)",
                    ["rpm-ostree", "reset"],
                    requires_root=True,
                    undo="rpm-ostree rollback  (the prior deployment is still bootable)",
                ),
            ],
        ), scope)

    if strategy == "microos":
        return _filter(ResetPlan(
            strategy="openSUSE MicroOS / Aeon (transactional, btrfs)",
            reversible=True,
            summary="Transactional-update with btrfs snapshots: every change is a "
            "snapshot you can roll back to. Factory reset = roll back to the first.",
            prerequisites=common_prereq,
            tiers=[
                _user_tier(),
                Tier("packages", "Roll back the system",
                     "Returns to an earlier (or the first) transactional snapshot.",
                     [
                         "snapper list                       # find the earliest snapshot",
                         "sudo snapper rollback <number>     # roll back to it",
                         "sudo transactional-update cleanup  # drop old snapshots",
                         "reboot",
                     ]),
            ],
            actions=[
                ResetAction(
                    "Roll back to the last known-good snapshot",
                    ["snapper", "rollback"],
                    requires_root=True,
                    undo="snapper rollback <previous-number> (all snapshots are retained)",
                ),
            ],
        ), scope)

    if strategy == "guix":
        return _filter(ResetPlan(
            strategy="Guix System (declarative)",
            reversible=True,
            summary="Like NixOS: declarative generations you can roll back to.",
            prerequisites=common_prereq,
            tiers=[
                _user_tier(),
                Tier("packages", "Roll back / reconfigure",
                     "Return to a pristine system definition.",
                     [
                         "sudo guix system roll-back         # previous generation",
                         "sudo guix system reconfigure <pristine-config.scm>",
                         "guix gc                            # collect garbage",
                     ]),
            ],
            actions=[
                ResetAction(
                    "Roll back to the previous system generation",
                    ["guix", "system", "roll-back"],
                    requires_root=True,
                    undo="guix system switch-generation <n> (generations are retained)",
                ),
            ],
        ), scope)

    if strategy == "macos":
        return _filter(ResetPlan(
            strategy="macOS",
            reversible=False,
            summary="macOS has a built-in factory reset ('Erase All Content and "
            "Settings') that is the correct, supported path — far safer than "
            "deleting files by hand.",
            prerequisites=["Back up with Time Machine first."],
            tiers=[
                _user_tier(),
                Tier("system", "Full erase (recommended)",
                     "The supported factory reset.",
                     [
                         "System Settings → General → Transfer or Reset → Erase All Content and Settings",
                         "Or boot into Recovery (⌘R) → Disk Utility → erase → reinstall macOS.",
                     ]),
            ],
        ), scope)

    # traditional
    distro = current_distro()
    pkg_steps: List[str]
    if which("apt-get"):
        pkg_steps = [
            "apt-mark showmanual > ~/manual-packages.txt   # review what you added",
            "Remove packages you installed, keeping the base seed; then:",
            "sudo apt-get autoremove --purge && sudo apt-get clean",
            "There is no supported 'reset to install state' — a reinstall is the reliable path.",
        ]
    elif which("dnf"):
        pkg_steps = [
            "dnf history list                 # find the first (install) transaction",
            "sudo dnf history rollback 1      # undo everything since install (best effort)",
            "sudo dnf autoremove && sudo dnf distro-sync",
        ]
    elif which("pacman"):
        pkg_steps = [
            "pacman -Qqe > ~/explicit-packages.txt   # your explicit installs",
            "Reduce to base:  pacman -Qqe | grep -vx -f <(pacman -Qqg base base-devel) | sudo pacman -Rns -",
            "Restore packaged configs:  sudo pacman -Qkk  then reinstall changed pkgs.",
        ]
    else:
        pkg_steps = ["Use your package manager to remove non-base packages; no universal reset exists."]

    return _filter(ResetPlan(
        strategy=f"Traditional distribution ({distro or current_os()})",
        reversible=False,
        summary="Traditional distros have NO true factory reset. The reliable "
        "options are (a) restore a pre-existing snapshot/backup, or (b) reinstall. "
        "The steps below approximate a reset but cannot guarantee an install-clean state.",
        prerequisites=common_prereq + [
            "STRONGLY consider a reinstall or snapshot restore instead of the steps below.",
        ],
        tiers=[
            _user_tier(distro),
            Tier("packages", "Approximate package reset",
                 "Removes user-installed packages; cannot perfectly restore the install set.",
                 pkg_steps),
            Tier("system", "Reset system configuration",
                 "Restore /etc toward packaged defaults.",
                 [
                     "Run cleanix's config-residue cleaner:  sudo cleanix clean --only config_leftovers --execute",
                     "Review remaining /etc changes against packaged defaults and revert them.",
                     "Re-run cleanix aggressively:  cleanix clean --all-users --execute "
                     "(after enabling include_offline_repos / purge_unused_locales if desired).",
                 ]),
        ],
    ), scope)


def _filter(plan: ResetPlan, scope: str) -> ResetPlan:
    if scope == "full":
        return plan
    wanted = {scope}
    if scope == "system":
        wanted = {"user", "packages", "system"}
    if scope == "packages":
        wanted = {"user", "packages"}
    plan.tiers = [t for t in plan.tiers if t.key in wanted]
    return plan
