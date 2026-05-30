#!/usr/bin/env python3
"""
Tests for status file management features (prune, launch status, etc.).
"""

import sys
import unittest
import tempfile
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# After `pip install -e .` in CI (or locally), the package is properly importable.
# Use clean imports from the installed package (no more fragile direct .py loading hacks).
from code_delegation_harness import prune_completed_status_files, _make_delegate_status, _write_status_file
from code_delegation_harness.harness import _print_dry_run_preview


class TestStatusFilePruning(unittest.TestCase):
    def test_prune_removes_old_completed_status(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # Create an old completed status file
            old_run_id = "old12345"
            old_sf = td / f".cdh-run-{old_run_id}.status"
            old_data = _make_delegate_status(old_run_id, "old-run", "some task", str(td), "grok-build", "completed")
            old_data["ended_at"] = (datetime.now() - timedelta(days=10)).isoformat()
            _write_status_file(old_sf, old_data)

            # Create a recent completed one (should not be pruned)
            recent_run_id = "recent1"
            recent_sf = td / f".cdh-run-{recent_run_id}.status"
            recent_data = _make_delegate_status(recent_run_id, "recent-run", "task", str(td), "grok-build", "completed")
            recent_data["ended_at"] = datetime.now().isoformat()
            _write_status_file(recent_sf, recent_data)

            # Run prune (older than 7 days)
            prune_completed_status_files(str(td), max_age_days=7)

            self.assertFalse(old_sf.exists(), "Old completed status should have been pruned")
            self.assertTrue(recent_sf.exists(), "Recent completed status should remain")

    def test_prune_ignores_active_and_non_status_files(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # Active (waiting) status
            active_sf = td / ".cdh-run-active99.status"
            active_data = _make_delegate_status("active99", None, "task", str(td), "grok-build", "waiting")
            _write_status_file(active_sf, active_data)

            # Random file
            other = td / "not-a-status.txt"
            other.write_text("ignore me")

            prune_completed_status_files(str(td), max_age_days=1)

            self.assertTrue(active_sf.exists())
            self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDryRunPreview(unittest.TestCase):
    def test_dry_run_does_not_write_files(self):
        """Dry-run mode must never create status files or output artifacts."""
        import tempfile
        import argparse
        import sys
        from io import StringIO

        with tempfile.TemporaryDirectory() as td:
            # Build fake args
            args = argparse.Namespace()
            args.task = "Test dry run safety"
            args.target_dir = td
            args.model = "grok-build"
            args.timeout = 1800
            args.max_turns = 60
            args.wait_for_completion = False
            args.max_wait = 7200
            args.poll_interval = 60
            args.run_name = "dry-run-safety-test"
            args.context = None
            args.constraints = None
            args.output_file = "/tmp/should-not-be-created.json"
            args.dry_run = True

            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                _print_dry_run_preview(args, td)
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            # Should mention it's a dry run
            self.assertIn("DRY RUN", output)
            self.assertIn("no inner delegation will be launched", output)

            # No status file should have been created
            status_files = list(Path(td).glob(".cdh-run-*.status"))
            self.assertEqual(len(status_files), 0, "Dry-run must not create any status files")


if __name__ == "__main__":
    unittest.main(verbosity=2)
