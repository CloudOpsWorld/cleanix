"""Cleanix test suite — core safety, engine, config, reset and quarantine."""

import os
from pathlib import Path

import pytest

from cleanix.cleaners.base import SCOPE_SYSTEM
from cleanix.config import Config, coerce_value
from cleanix import reset
from cleanix.core import context, quarantine, safety
from cleanix.core.context import TargetUser
from cleanix.core.engine import Engine
from cleanix.core.models import CleanableItem, CleanerReport, ItemKind, ScanResult
from cleanix.core.platform import ALL, LINUX, MACOS, supports
from cleanix.core.registry import build_cleaners
from cleanix.core.utils import human_size, surplus_after_keeping


# --------------------------------------------------------------------------- safety
@pytest.mark.parametrize("bad", ["/", "/etc", "/usr", "/boot", "/System", "/Library"])
def test_protected_system_paths_refused(bad):
    assert not safety.is_safe_to_delete(bad)


def test_home_and_config_protected():
    home = os.path.expanduser("~")
    assert not safety.is_safe_to_delete(home)
    assert not safety.is_safe_to_delete(home + "/.config")
    assert safety.is_safe_to_delete(home + "/.cache/some-app")


def test_ancestor_of_protected_refused(tmp_path):
    # A path that contains a protected root must be refused.
    assert not safety.is_safe_to_delete("/")


def test_protected_globs(tmp_path):
    safety.set_protected_globs([str(tmp_path) + "/keep*"])
    try:
        assert not safety.is_safe_to_delete(tmp_path / "keepme")
        assert safety.is_safe_to_delete(tmp_path / "other")
    finally:
        safety.set_protected_globs([])


def test_safe_rmtree_refuses_protected():
    with pytest.raises(safety.UnsafePathError):
        safety.safe_rmtree("/etc")


# --------------------------------------------------------------------------- engine
def _item(path, size=100, **kw):
    return CleanableItem("t", "junk", size, ItemKind.PATH, str(path), **kw)


def test_dry_run_does_not_delete(tmp_path):
    d = tmp_path / "d"; d.mkdir(); (d / "f").write_text("x")
    res = Engine([]).clean([_item(d)], dry_run=True)
    assert d.exists() and res.freed == 100 and res.removed_count == 0


def test_execute_deletes(tmp_path):
    d = tmp_path / "d"; d.mkdir(); (d / "f").write_text("x")
    res = Engine([]).clean([_item(d)], dry_run=False)
    assert not d.exists() and res.removed_count == 1


def test_report_only_never_deleted(tmp_path):
    d = tmp_path / "d"; d.mkdir()
    res = Engine([]).clean([_item(d, report_only=True)], dry_run=False)
    assert d.exists() and not res.outcomes[0].removed


def test_root_item_skipped_without_privilege(tmp_path):
    d = tmp_path / "d"; d.mkdir()
    res = Engine([]).clean([_item(d, requires_root=True)],
                           dry_run=False, allow_root_items=False)
    assert d.exists() and "root" in (res.outcomes[0].error or "")


def test_protected_path_item_refused():
    res = Engine([]).clean([_item("/etc", size=0)], dry_run=False)
    assert not res.outcomes[0].removed and os.path.isdir("/etc")


def test_parallel_scan_matches_sequential():
    eng = Engine(build_cleaners(Config()))
    seq = {r.cleaner_id for r in eng.scan(parallel=False).reports}
    par = {r.cleaner_id for r in eng.scan(parallel=True).reports}
    assert seq == par


# --------------------------------------------------------------------------- models
def test_scanresult_splits_cleanable_and_report_only():
    a = _item("/tmp/a"); b = _item("/tmp/b", report_only=True)
    sr = ScanResult([CleanerReport("t", "t", "", [a, b])])
    assert sr.cleanable_items() == [a]
    assert sr.report_only_items() == [b]
    assert sr.cleanable_size == 100 and sr.report_only_size == 100


# --------------------------------------------------------------------------- retention
def test_surplus_after_keeping(tmp_path):
    files = []
    for i in range(5):
        f = tmp_path / f"b{i}"; f.write_text("x")
        os.utime(f, (1000 + i, 1000 + i))
        files.append(f)
    surplus = surplus_after_keeping(files, 2)
    assert {p.name for p in surplus} == {"b0", "b1", "b2"}   # 3 oldest
    assert surplus_after_keeping(files, 0) == sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


# --------------------------------------------------------------------------- config
def test_coerce_value_types():
    assert coerce_value("keep_kernels", "4") == 4
    assert coerce_value("remove_old_kernels", "off") is False
    assert coerce_value("temp_min_age_days", "1.5") == 1.5
    assert coerce_value("browsers", "a, b ,c") == ["a", "b", "c"]
    with pytest.raises(ValueError):
        coerce_value("remove_old_kernels", "maybe")
    with pytest.raises(KeyError):
        coerce_value("nonsense", "1")


def test_config_override_roundtrip(tmp_path):
    from cleanix import config as cfgmod

    p = tmp_path / "config.yaml"
    cfgmod.write_user_override("keep_kernels", 5, path=p)
    assert cfgmod.read_user_overrides(p)["keep_kernels"] == 5
    assert cfgmod.remove_user_override("keep_kernels", path=p) is True
    assert "keep_kernels" not in cfgmod.read_user_overrides(p)


# --------------------------------------------------------------------------- platform
def test_platform_supports():
    from cleanix.core.platform import current_os

    assert supports((ALL,))
    assert supports((current_os(),))
    assert not supports(("nonexistent-os",))


# --------------------------------------------------------------------------- context
def test_multi_user_iteration_and_dedup(tmp_path):
    from cleanix.cleaners.base import Cleaner, SCOPE_USER

    h1 = tmp_path / "u1"; (h1 / ".cache" / "j").mkdir(parents=True)
    h2 = tmp_path / "u2"; (h2 / ".cache" / "j").mkdir(parents=True)
    u1 = TargetUser("u1", h1, 4001, 4001, False)
    u2 = TargetUser("u2", h2, 4002, 4002, False)
    context._cached_targets = [u1, u2]
    try:
        class Shared(Cleaner):
            id = "shared"; scope = SCOPE_USER
            def find_items(self):
                yield CleanableItem("shared", "x", 0, ItemKind.PATH, "/usr/local/bin/tool")
        # shared path yielded per user collapses to one
        assert len(Shared(Config()).scan().items) == 1
    finally:
        context._cached_targets = None


# --------------------------------------------------------------------------- reset
@pytest.mark.parametrize("strategy,cmd0", [
    ("nixos", ["nixos-rebuild", "switch", "--rollback"]),
    ("ostree", ["rpm-ostree", "reset"]),
    ("guix", ["guix", "system", "roll-back"]),
])
def test_reset_actions(monkeypatch, strategy, cmd0):
    monkeypatch.setattr(reset, "_detect_strategy", lambda: strategy)
    plan = reset.build_plan("full")
    assert plan.reversible and plan.actions[0].command == cmd0


def test_reset_traditional_not_reversible(monkeypatch):
    monkeypatch.setattr(reset, "_detect_strategy", lambda: "traditional")
    plan = reset.build_plan("full")
    assert not plan.reversible and not plan.actions


def test_execute_actions_stops_on_failure(monkeypatch):
    monkeypatch.setattr(reset, "_detect_strategy", lambda: "ostree")
    plan = reset.build_plan("full")
    plan.actions.append(reset.ResetAction("second", ["true"]))
    calls = []
    def runner(cmd):
        calls.append(cmd)
        return 1 if cmd == ["rpm-ostree", "reset"] else 0
    results = reset.execute_actions(plan, runner)
    assert len(results) == 1 and calls == [["rpm-ostree", "reset"]]  # stopped


# --------------------------------------------------------------------------- quarantine
@pytest.fixture
def qroot(tmp_path, monkeypatch):
    root = tmp_path / "quar"
    monkeypatch.setattr(quarantine, "quarantine_root", lambda: root)
    return root


def test_quarantine_roundtrip(tmp_path, qroot):
    junk = tmp_path / "junk"; junk.mkdir(); (junk / "f").write_text("x" * 500)
    run = quarantine.new_run()
    Engine([]).clean([_item(junk, 500)], dry_run=False, quarantine=run)
    run.save()
    assert not junk.exists()
    assert any(r["run_id"] == run.run_id for r in quarantine.list_runs())

    res = quarantine.restore(run.run_id)
    assert junk.exists() and (junk / "f").read_text() == "x" * 500
    assert not res["failed"]


def test_quarantine_purge(tmp_path, qroot):
    junk = tmp_path / "junk"; junk.mkdir(); (junk / "f").write_text("y" * 300)
    run = quarantine.new_run()
    Engine([]).clean([_item(junk, 300)], dry_run=False, quarantine=run)
    run.save()
    freed = quarantine.purge_all()
    assert freed > 0 and quarantine.total_size() == 0


# --------------------------------------------------------------------------- opt-in / memory
def test_memory_cleaners_are_opt_in_only():
    default_ids = {c.id for c in build_cleaners(Config())}
    assert "memory" not in default_ids and "swap" not in default_ids
    forced = {c.id for c in build_cleaners(Config(), only=["memory", "swap"])}
    assert "memory" in forced


def test_swap_guard_refuses_when_ram_too_low(monkeypatch):
    from cleanix.cleaners import memory

    # Swap used (2G) with little available RAM (1G) → must NOT offer swapoff.
    monkeypatch.setattr(memory, "_meminfo", lambda: {
        "SwapTotal": 2 * 1024**3, "SwapFree": 0,
        "MemAvailable": 1 * 1024**3,
    })
    assert list(memory.SwapReclaimCleaner(Config()).find_items()) == []
    # Plenty of RAM (8G) → offers it.
    monkeypatch.setattr(memory, "_meminfo", lambda: {
        "SwapTotal": 2 * 1024**3, "SwapFree": 0,
        "MemAvailable": 8 * 1024**3,
    })
    items = list(memory.SwapReclaimCleaner(Config()).find_items())
    assert len(items) == 1 and "swapoff" in " ".join(items[0].command)


# --------------------------------------------------------------------------- completion
@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_generates(shell):
    from cleanix.completion import generate

    script = generate(shell)
    assert "cleanix" in script and "scan" in script and len(script) > 100


# --------------------------------------------------------------------------- utils
def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(1024) == "1.0 KiB"
    assert human_size(1024 ** 3) == "1.0 GiB"
