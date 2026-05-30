#!/usr/bin/env python3
"""
Minimal unit tests for normalize_result and its extracted helpers.

These tests cover the status and diff paths post-refactor without altering
public behavior. Run with: python -m unittest tests.test_normalize_result
or python tests/test_normalize_result.py
"""

import sys
import unittest
from pathlib import Path

# Allow importing the script under test (no package yet)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from grok_delegate import normalize_result, _determine_status, _compute_diffs_and_stats, render_human_report


class TestNormalizeResult(unittest.TestCase):
    def test_no_changes_path(self):
        """Exercise no_changes status when delegation reports zero file ops."""
        raw = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Inspected only.\nFILES_CREATED:\nFILES_MODIFIED:\nFILES_DELETED:\n=== END SUMMARY ===",
            "exit_code": 0,
        }
        result = normalize_result(raw, target_dir=None)
        self.assertEqual(result["status"], "no_changes")
        self.assertTrue(result["success"])
        self.assertTrue(result["changes"]["no_changes_made"])
        self.assertNotIn("diffs", result)
        self.assertNotIn("change_stats", result)

    def test_failure_and_error_categorization(self):
        """Wrapper error and nonzero exit should produce failure + categorized errors."""
        raw = {
            "error": "Grok call timed out",
            "exit_code": -1,
            "text": "partial output before timeout",
        }
        result = normalize_result(raw, target_dir=None)
        self.assertEqual(result["status"], "failure")
        self.assertFalse(result["success"])
        self.assertTrue(any(e["type"] == "wrapper_error" for e in result.get("errors", [])))
        self.assertTrue(any(e["type"] == "nonzero_exit" for e in result.get("errors", [])))

    def test_partial_success_via_stderr(self):
        """Presence of stderr with changes yields partial_success (pre-error-categorization path)."""
        raw = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Made a small edit.\nFILES_CREATED:\nFILES_MODIFIED:\n- src/foo.py (minor tweak)\nFILES_DELETED:\n=== END SUMMARY ===",
            "exit_code": 0,
            "stderr": "Warning: something non-fatal",
        }
        result = normalize_result(raw, target_dir=None)
        self.assertEqual(result["status"], "partial_success")
        self.assertTrue(result["success"])
        self.assertIn("errors", result)  # surfaced from categorization

    def test_diff_logic_skipped_without_target_dir(self):
        """When target_dir is falsy, diff/stats extraction is skipped (no crash, no keys)."""
        raw = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Edited one file.\nFILES_CREATED:\nFILES_MODIFIED:\n- bar.py\nFILES_DELETED:\n=== END SUMMARY ===",
            "exit_code": 0,
        }
        result = normalize_result(raw, target_dir=None)
        self.assertEqual(result["status"], "success")
        self.assertNotIn("diffs", result)
        self.assertNotIn("change_stats", result)
        self.assertEqual(result["changes"]["modified"], ["bar.py"])

    def test_helpers_directly(self):
        """Sanity check on the extracted helpers (new internal API surface for modularity)."""
        # Status helper
        self.assertEqual(_determine_status({"exit_code": 0}, has_changes=False), "no_changes")
        self.assertEqual(_determine_status({"error": "boom"}, has_changes=True), "failure")
        self.assertEqual(_determine_status({"stderr": "x", "exit_code": 0}, has_changes=True), "partial_success")

        # Diff helper: no target or no modified -> empty (now 4-tuple: diffs, stats, descs, previews)
        self.assertEqual(_compute_diffs_and_stats(None, ["a.py"]), ({}, {}, {}, {}))
        self.assertEqual(_compute_diffs_and_stats("/tmp", []), ({}, {}, {}, {}))

    def test_observations_and_diff_previews(self):
        """Observations captured for read-only runs; diff_previews appear for real changes when target_dir allows."""
        # Read-only / no-change with observations
        raw_noop = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Reviewed the login module for security issues.\nFILES_CREATED:\nFILES_MODIFIED:\nFILES_DELETED:\nOBSERVATIONS:\n- Inspected auth.py, login.py, and test_login.py\n- Session handling looks solid; one TODO noted around refresh token rotation\n=== END SUMMARY ===",
            "exit_code": 0,
        }
        result = normalize_result(raw_noop, target_dir=None)
        self.assertEqual(result["status"], "no_changes")
        self.assertIn("observations", result)
        self.assertIn("refresh token rotation", result.get("observations", ""))

        # With changes: even without real git, we still parse and would attach previews if git succeeded
        raw_change = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Tightened error handling in the validator.\nFILES_CREATED:\nFILES_MODIFIED:\n- src/validators.py (added stricter checks)\nFILES_DELETED:\n=== END SUMMARY ===",
            "exit_code": 0,
        }
        result2 = normalize_result(raw_change, target_dir=None)
        self.assertEqual(result2["status"], "success")
        # No previews without target_dir/git, but field presence is safe
        self.assertNotIn("diff_previews", result2)

    def test_render_human_report_produces_usable_markdown(self):
        """The end-result review report must always be a readable Markdown string with key sections."""
        raw = {
            "text": "=== DELEGATION SUMMARY ===\nSUMMARY: Added two helper functions and improved error paths.\nFILES_CREATED:\nFILES_MODIFIED:\n- src/utils.py (+18, -3, error handling improved, docstrings added)\nFILES_DELETED:\nOBSERVATIONS:\n- Two other call sites could benefit from the same pattern.\n=== END SUMMARY ===",
            "exit_code": 0,
        }
        result = normalize_result(raw, target_dir=None)
        report = render_human_report(result)

        self.assertIsInstance(report, str)
        self.assertIn("# Delegation Report", report)
        self.assertIn("## Files Modified", report)
        self.assertIn("## How to Review This Change", report)
        self.assertIn("Observations / Key Findings", report)
        self.assertIn("src/utils.py", report)
        self.assertIn("error handling improved", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
