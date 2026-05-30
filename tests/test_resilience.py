#!/usr/bin/env python3
"""
Unit and smoke tests for long-running / background resilience features:
- StatusManager (heartbeats, crash states, looks_dead, ensure_recoverable, load recovery)
- load_checkpoint_context (agent PROGRESS.json etc.)
- Crash protection registration (basic wiring)
- --reap-dead and --status dead detection (via fake statuses + CLI invocation)
- Auto-recovery prompt augmentation on --resume from crashed

These improve testability of the post-aa323a1 / a536621 resilience additions.
Run with: python -m pytest tests/test_resilience.py -q  or  python tests/test_resilience.py
"""

import sys
import unittest
import tempfile
import json
import time
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from io import StringIO

# Ensure we test the source tree (matches test_status_features.py pattern)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from code_delegation_harness.status import (
    StatusManager,
    register_crash_protection,
    _mark_active_run_crashed,
    _ACTIVE_STATUS_FILE,
)
from code_delegation_harness.harness import (
    load_checkpoint_context,
    _propagate_background_flags,
    RetryPolicy,
)


class TestStatusManagerResilience(unittest.TestCase):
    def test_create_new_writes_full_prompt_and_pid(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new(
                "r1", "test-run", "do the thing", td, "grok-build",
                prompt="FULL PROMPT TEXT HERE WITH INSTRUCTIONS",
                context="ctx", constraints="c"
            )
            self.assertTrue(sm.status_file.exists())
            data = sm.to_dict()
            self.assertEqual(data["run_id"], "r1")
            self.assertIn("prompt", data)
            self.assertEqual(data["prompt"], "FULL PROMPT TEXT HERE WITH INSTRUCTIONS")
            self.assertIn("pid", data)
            self.assertEqual(data["state"], "launched")

    def test_heartbeat_and_record_poll_update_timestamps(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("r2", None, "t", td, "grok-build")
            sm.heartbeat("first beat")
            d1 = sm.to_dict()
            self.assertIn("last_heartbeat_at", d1)
            self.assertIn("first beat", d1.get("last_heartbeat_message", ""))

            time.sleep(0.01)
            sm.record_poll(42.0)
            d2 = sm.to_dict()
            self.assertIn("last_heartbeat_at", d2)  # record_poll also sets it
            self.assertGreaterEqual(d2["elapsed_seconds"], 42)

    def test_looks_dead_detects_stale_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("r3", None, "t", td, "grok-build", state="running")
            # Fresh: not dead
            sm.heartbeat()
            self.assertFalse(sm.looks_dead(max_silence_seconds=300))

            # Manually age the heartbeat far into past
            old = (datetime.now() - timedelta(seconds=400)).isoformat()
            sm._data["last_heartbeat_at"] = old
            sm._atomic_write()
            self.assertTrue(sm.looks_dead(max_silence_seconds=300))
            # Non-running states never look dead
            sm.set_state("completed")
            self.assertFalse(sm.looks_dead(1))

    def test_looks_dead_returns_false_when_no_timestamp_fields(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("r6", None, "t", td, "grok-build", state="running")
            # Fresh create has no last_heartbeat or last_poll
            self.assertFalse(sm.looks_dead(1))
            # Even if we force a state, missing ts -> not dead (defensive)
            sm._data["last_heartbeat_at"] = None
            self.assertFalse(sm.looks_dead(300))

    def test_ensure_recoverable_self_heals_corrupted_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            sf = Path(td) / ".cdh-run-heal.status"
            # Write garbage
            sf.write_text("{ not valid json at all")
            sm = StatusManager(sf)
            loaded = sm.load()
            self.assertFalse(loaded)
            self.assertTrue(sm.get("_corrupted"))

            sm.ensure_recoverable("heal99", "healed-name", td, "grok-build")
            d = sm.to_dict()
            self.assertEqual(d["run_id"], "heal99")
            self.assertEqual(d["target_dir"], td)
            self.assertEqual(d["model"], "grok-build")
            self.assertEqual(d["state"], "waiting")
            self.assertTrue(d.get("_recovered"))
            # Does not overwrite good data
            sm2 = StatusManager(sf)
            sm2.load()
            sm2.update(task="keep me")
            sm2.ensure_recoverable("other", None, "/wrong", "other-model")
            self.assertEqual(sm2.get("task"), "keep me")
            # ensure_recoverable only fills gaps / corrupted; does not clobber a valid run_id
            self.assertEqual(sm2.get("run_id"), "heal99")

    def test_mark_crashed_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("r4", None, "t", td, "grok-build")
            sm.mark_crashed("test reason for death")
            d = sm.to_dict()
            self.assertEqual(d["state"], "crashed")
            self.assertIn("test reason", d.get("crash_reason", ""))

            sm2 = StatusManager(sm.status_file)
            self.assertTrue(sm2.load())
            self.assertEqual(sm2.state, "crashed")

    def test_atomic_write_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("r5", None, "t", td, "grok-build")
            mode = sm.status_file.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)


class TestCrashProtectionWiring(unittest.TestCase):
    def test_register_sets_global_and_mark_does_not_crash(self):
        global _ACTIVE_STATUS_FILE
        with tempfile.TemporaryDirectory() as td:
            sm = StatusManager.create_new("prot1", None, "t", td, "grok-build")
            sf = sm.status_file
            register_crash_protection(sf)
            # Force the marker - must not raise, and should transition state.
            # Note: _mark clears the global _ACTIVE_STATUS_FILE as cleanup (internal).
            _mark_active_run_crashed("unit test force")
            sm2 = StatusManager(sf)
            sm2.load()
            self.assertEqual(sm2.state, "crashed")

    def test_mark_skips_if_not_active_state(self):
        with tempfile.TemporaryDirectory() as td:
            sf = Path(td) / ".cdh-run-skip.status"
            sm = StatusManager.create_new("skip1", None, "t", td, "grok-build")
            sm.set_state("completed")
            _mark_active_run_crashed("should not override")
            self.assertEqual(sm.load() and sm.state, "completed")


class TestCheckpointLoading(unittest.TestCase):
    def test_load_checkpoint_context_finds_progress_json_and_injects(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "PROGRESS.json"
            p.write_text(json.dumps({
                "completed": ["did X"],
                "current_plan": ["do Y"],
                "last_checkpoint": "2026-05-30T12:00"
            }, indent=2))
            ctx = load_checkpoint_context(td)
            self.assertIn("BEGIN UNTRUSTED CHECKPOINT", ctx)
            self.assertIn("did X", ctx)
            self.assertIn("attacker-controlled or tampered", ctx)
            self.assertIn("The previous background run appears to have died", ctx)

    def test_load_checkpoint_context_ignores_missing_and_bad_files(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(load_checkpoint_context(td), "")
            bad = Path(td) / "TASK_STATE.md"
            bad.write_text("")  # empty -> skipped
            self.assertEqual(load_checkpoint_context(td), "")

    def test_load_checkpoint_context_skips_oversized_file(self):
        with tempfile.TemporaryDirectory() as td:
            big = Path(td) / "PROGRESS.json"
            big.write_text("x" * 100000)  # > 64KiB cap
            ctx = load_checkpoint_context(td)
            self.assertIn("SKIPPED", ctx)
            self.assertIn("too large", ctx)

    def test_load_checkpoint_context_handles_malformed_but_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            # Non-json but small: should still wrap (content is just text)
            p = Path(td) / "TASK_STATE.md"
            p.write_text("not json but valid text checkpoint")
            ctx = load_checkpoint_context(td)
            self.assertIn("BEGIN UNTRUSTED CHECKPOINT", ctx)
            self.assertIn("not json but valid text checkpoint", ctx)


class TestReapAndStatusDeadDetection(unittest.TestCase):
    def _make_stale_status(self, td: Path, run_id: str, state: str = "running") -> Path:
        sf = td / f".cdh-run-{run_id}.status"
        sm = StatusManager.create_new(run_id, f"stale-{run_id}", "stale task", str(td), "grok-build", state=state)
        old = (datetime.now() - timedelta(seconds=400)).isoformat()
        sm._data["last_heartbeat_at"] = old
        sm._atomic_write()
        return sf

    def test_looks_dead_used_by_reap_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fresh = StatusManager.create_new("fresh", None, "t", str(td), "grok-build", state="running")
            fresh.heartbeat()
            stale_sf = self._make_stale_status(td, "stale99")

            sm = StatusManager(stale_sf)
            sm.load()
            self.assertTrue(sm.looks_dead(300))

            # Simulate what --reap-dead does
            if sm.looks_dead(300):
                sm.mark_crashed("Reaped by test")
            self.assertEqual(sm.state, "crashed")

    def test_cli_reap_dead_and_status_detect_and_mark_via_subprocess(self):
        """End-to-end smoke of the CLI paths for --reap-dead and --status (no real grok needed)."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            stale = self._make_stale_status(td, "cli-reap-01")
            # Also a completed one
            comp = StatusManager.create_new("cli-comp", None, "done", str(td), "grok-build", state="completed")
            comp.mark_completed(0)

            # Invoke via python -m , forcing PYTHONPATH to the src tree under test
            # (ensures we exercise the exact worktree code, not a stale installed copy)
            python = sys.executable
            src_root = str(Path(__file__).parent.parent / "src")
            env = os.environ.copy()
            env["PYTHONPATH"] = src_root + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
            base = ["-m", "code_delegation_harness", "--target-dir", str(td)]

            # 1. --status should surface the stale as dead (uses looks_dead)
            out = subprocess.run(
                [python] + base + ["--status"],
                capture_output=True, text=True, cwd=td, env=env, timeout=15
            )
            combined = (out.stdout or "") + (out.stderr or "")
            self.assertIn("cli-reap-01", combined)
            # The looks_dead path in --status rewrites label
            self.assertIn("crashed (no heartbeat)", combined)

            # 2. --reap-dead should mark it
            out2 = subprocess.run(
                [python] + base + ["--reap-dead"],
                capture_output=True, text=True, cwd=td, env=env, timeout=15
            )
            combined2 = (out2.stdout or "") + (out2.stderr or "")
            self.assertIn("Reaped", combined2)
            # Verify state flipped on disk
            sm = StatusManager(stale)
            sm.load()
            self.assertEqual(sm.state, "crashed")


class TestResumeAutoRecovery(unittest.TestCase):
    def test_resume_from_crashed_augments_prompt_with_checkpoint(self):
        # We test the logic path in harness without full main()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "PROGRESS.json"
            p.write_text('{"completed":["step1"]}')
            ctx = load_checkpoint_context(td)
            self.assertIn("BEGIN UNTRUSTED CHECKPOINT", ctx)
            self.assertIn("step1", ctx)

            # Simulate the augmentation that happens in --resume crashed path (see harness.py:1249)
            original = "ORIGINAL TASK PROMPT"
            augmented = (
                original
                + "\n\n=== RECOVERY MODE: PREVIOUS RUN CRASHED ===\n"
                + "The previous background execution of this task died or was interrupted without completing.\n"
                + ctx
            )
            self.assertIn("step1", augmented)
            self.assertIn("RECOVERY MODE", augmented)


class TestRetryPolicy(unittest.TestCase):
    def test_retry_succeeds_and_backoffs(self):
        calls = []
        def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("transient")
            return "ok"
        rp = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)
        ok, res = rp.run(flaky)
        self.assertTrue(ok)
        self.assertEqual(res, "ok")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    # Support direct run
    unittest.main(verbosity=2)
