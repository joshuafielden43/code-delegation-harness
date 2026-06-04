"""Tests for research dir pruning (prune_research_dir)."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.code_delegation_harness.trace import (
    ensure_research_dir,
    prune_research_dir,
    write_output_to_research,
    write_trace,
    build_trace_from_result,
    AttackBlock,
    VerdictBlock,
    RunRecord,
)


class TestPruneResearchDir(unittest.TestCase):

    def _write_artifact(self, research_dir: str, name: str, age_days: float) -> str:
        """Create a file and backdate its mtime by age_days."""
        p = Path(research_dir) / name
        p.write_text("content")
        p.chmod(0o600)
        old_mtime = time.time() - age_days * 86400
        os.utime(p, (old_mtime, old_mtime))
        return str(p)

    def test_prune_removes_old_traces(self):
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)
            ba = Path(d) / "build-attempts"

            # Write one old and one recent trace
            old = ba / "old-trace.yaml"
            old.write_text("---\nid: old")
            old.chmod(0o600)
            recent = ba / "recent-trace.yaml"
            recent.write_text("---\nid: recent")
            recent.chmod(0o600)

            # Backdate old trace to 10 days ago
            old_mtime = time.time() - 10 * 86400
            os.utime(old, (old_mtime, old_mtime))

            result = prune_research_dir(d, max_age_days=7)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(result["kept"], 1)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())

    def test_prune_removes_old_stdout_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)

            old_out = self._write_artifact(d, "run1-pass1-stdout.txt", age_days=8)
            old_err = self._write_artifact(d, "run1-pass1-stderr.txt", age_days=8)
            new_out = self._write_artifact(d, "run2-pass1-stdout.txt", age_days=1)

            result = prune_research_dir(d, max_age_days=7)
            self.assertEqual(result["removed"], 2)
            self.assertEqual(result["kept"], 1)
            self.assertFalse(Path(old_out).exists())
            self.assertFalse(Path(old_err).exists())
            self.assertTrue(Path(new_out).exists())

    def test_prune_nonexistent_dir_returns_zeros(self):
        result = prune_research_dir("/tmp/definitely-does-not-exist-xyz123", max_age_days=7)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["kept"], 0)
        self.assertEqual(result["errors"], 0)

    def test_prune_empty_dir_returns_zeros(self):
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)
            result = prune_research_dir(d, max_age_days=7)
            self.assertEqual(result["removed"], 0)
            self.assertEqual(result["kept"], 0)

    def test_prune_keeps_recent_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)
            ba = Path(d) / "build-attempts"
            for i in range(3):
                f = ba / f"trace-{i}.yaml"
                f.write_text(f"---\nid: {i}")
                f.chmod(0o600)
                # All recent (1 day old)
                os.utime(f, (time.time() - 86400, time.time() - 86400))
            result = prune_research_dir(d, max_age_days=7)
            self.assertEqual(result["removed"], 0)
            self.assertEqual(result["kept"], 3)

    def test_prune_default_age_is_seven_days(self):
        """Calling without max_age_days uses 7-day default."""
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)
            ba = Path(d) / "build-attempts"
            old = ba / "eight-day-old.yaml"
            old.write_text("---\nid: old")
            old.chmod(0o600)
            os.utime(old, (time.time() - 8 * 86400,) * 2)

            result = prune_research_dir(d)  # default 7 days
            self.assertEqual(result["removed"], 1)

    def test_prune_returns_error_count_on_unlink_issue(self):
        """Errors during unlink are counted, not raised."""
        with tempfile.TemporaryDirectory() as d:
            ensure_research_dir(d)
            ba = Path(d) / "build-attempts"
            old = ba / "old.yaml"
            old.write_text("---\nid: x")
            old.chmod(0o600)
            os.utime(old, (time.time() - 10 * 86400,) * 2)

            with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
                result = prune_research_dir(d, max_age_days=7)
            self.assertGreaterEqual(result["errors"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
