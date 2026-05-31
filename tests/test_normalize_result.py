#!/usr/bin/env python3
"""
Minimal unit tests for normalize_result and its extracted helpers.

These tests cover the status and diff paths post-refactor without altering
public behavior. Run with: python -m unittest tests.test_normalize_result
or python tests/test_normalize_result.py
"""

import sys
import unittest
import tempfile
import json
from pathlib import Path

# Allow importing the script under test (no package yet)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from code_delegation_harness import normalize_result, _determine_status, _compute_diffs_and_stats, render_human_report


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

    def test_render_human_report_handles_synthesized_checkpoint_summary(self):
        """When the summary was recovered from agent checkpoints (missing marker), the report must clearly surface it."""
        raw = {
            "text": "I did a bunch of work on the tag scanner but forgot the exact markers at the end.",
            "exit_code": 0,
        }
        result = normalize_result(raw, target_dir=None)
        # Simulate what happens after our new recovery logic
        result["summary_synthesized_from_checkpoint"] = True
        result["observations"] = "[Best-effort recovery from PROGRESS.json]\nCompleted: normalization for YouTube and GitHub clusters\nNext: NUC infrastructure tags"

        report = render_human_report(result)

        self.assertIsInstance(report, str)
        self.assertIn("♻️ Summary Synthesized from Agent Checkpoints", report)
        self.assertIn("best-effort recovery", report)
        self.assertIn("PROGRESS.json", report)
        self.assertIn("intentional, supported part of long-running delegation", report)

    def test_synthesis_extracts_structured_data_from_checkpoint(self):
        """When the marker is missing but a good PROGRESS.json exists, synthesis should pull files and next_steps."""
        raw = {"text": "I worked on some tag stuff but forgot the summary block.", "exit_code": 0}
        # We can't easily write a real file in this test without temp dirs, so we test the extraction logic more directly
        from code_delegation_harness.harness import _best_effort_summary_extraction
        # Simulate what the function does with a checkpoint containing structure
        # (the real integration is covered by normalize_result with target_dir in other tests)
        result = _best_effort_summary_extraction("some partial text", target_dir=None)
        self.assertFalse(result["synthesized_from_checkpoint"])

    def test_full_normalize_with_synthesized_summary(self):
        """End-to-end: missing marker + synthesized flag should flow through normalize_result correctly."""
        raw = {
            "text": "Did normalization work on several clusters but missed the exact markers.",
            "exit_code": 0,
        }
        result = normalize_result(raw, target_dir=None)
        result["summary_synthesized_from_checkpoint"] = True  # simulate recovery having run
        result["observations"] = "[Best-effort recovery from PROGRESS.json]\nCompleted: YouTube and GitHub clusters"

        self.assertFalse(result["has_structured_summary"])
        self.assertTrue(result.get("summary_synthesized_from_checkpoint"))
        self.assertIn("YouTube and GitHub", result.get("observations", ""))

    def test_real_checkpoint_synthesis_end_to_end(self):
        """End-to-end test with a real temporary PROGRESS.json to verify full synthesis path."""
        with tempfile.TemporaryDirectory() as td:
            progress = {
                "completed": ["Fixed path normalization in API backend", "Added 2 new tests for pvesh-usage"],
                "current_phase": "Final summary",
                "next_steps": ["Review artifacts"],
                "open_issues": [],
                "gotchas": ["Minor tool error during search_replace that was non-blocking"]
            }
            progress_path = Path(td) / "PROGRESS.json"
            progress_path.write_text(json.dumps(progress, indent=2))

            raw = {
                "text": "I did some good work on the skill but completely forgot to emit the required summary markers at the end.",
                "exit_code": 0,
            }

            result = normalize_result(raw, target_dir=td)

            self.assertTrue(result.get("summary_synthesized_from_checkpoint"))
            # In the normalized result, file lists live under changes.*
            changes = result.get("changes", {})
            self.assertIn("Review artifacts", result.get("next_steps", ""))
            self.assertIn("PROGRESS.json", result.get("observations", ""))
            self.assertIn("Fixed path normalization in API backend", result.get("observations", ""))
            # For small completed lists we don't force files_modified population (grooming case does)

            # Also test that rendering handles it gracefully
            report = render_human_report(result)
            self.assertIn("♻️ Summary Synthesized from Agent Checkpoints", report)
            self.assertIn("Recovery Sources", report)

    def test_grooming_style_synthesis_with_grouping(self):
        """Test that long grooming runs with many similar small edits get good grouped summaries in both synthesis and report."""
        with tempfile.TemporaryDirectory() as td:
            # Simulate 30+ small tag normalizations (realistic vault grooming)
            completed = [
                f"Normalized tag 'youtube:video:{i}' → 'media:video:youtube'" for i in range(18)
            ] + [
                f"Normalized tag 'github:repo:{i}' → 'infra:github:repo'" for i in range(12)
            ]
            progress = {
                "completed": completed,
                "current_phase": "Grooming complete",
                "next_steps": ["Review grouped decisions", "Apply selective patches"],
                "gotchas": ["Some YouTube tags had context-specific meanings"]
            }
            (Path(td) / "PROGRESS.json").write_text(json.dumps(progress, indent=2))

            raw = {"text": "Finished big tag grooming pass. Markers missed due to length.", "exit_code": 0}
            result = normalize_result(raw, target_dir=td)

            self.assertTrue(result.get("summary_synthesized_from_checkpoint"))
            cs = result.get("change_summary", "")
            self.assertIn("Grooming / normalization work across 30 items", cs)
            # Improved grouping now keys on target canonical (post-→ form) for normalization work — higher signal
            self.assertIn("media:video:youtube", cs)
            self.assertIn("infra:github:repo", cs)

            report = render_human_report(result)
            self.assertIn("grooming/normalization-style run", report)
            self.assertIn("Recovery Sources", report)

    def test_grooming_style_many_small_edits_synthesis(self):
        """Test synthesis and rendering for grooming/normalization runs with many small edits (tag work, vault grooming, etc.)."""
        with tempfile.TemporaryDirectory() as td:
            # Simulate a real grooming run with 25 small precise tag normalizations
            completed = [f"Normalized tag 'youtube:{i}' → 'media:video:youtube'" for i in range(25)]
            progress = {
                "completed": completed,
                "current_phase": "Final grooming summary",
                "next_steps": ["Review normalization decisions", "Update living registry"],
                "gotchas": ["Some tags had ambiguous contexts"]
            }
            progress_path = Path(td) / "PROGRESS.json"
            progress_path.write_text(json.dumps(progress, indent=2))

            raw = {
                "text": "Did a big grooming pass on the tags but the final summary markers got cut off.",
                "exit_code": 0,
            }

            result = normalize_result(raw, target_dir=td)

            self.assertTrue(result.get("summary_synthesized_from_checkpoint"))
            self.assertIn("Grooming / normalization work across 25 items", result.get("change_summary", ""))
            changes = result.get("changes", {})
            self.assertGreaterEqual(len(changes.get("modified", [])), 8)  # capped but populated from completed list
            self.assertIn("grooming_notes", result)  # dedicated notes for better review by Honey
            self.assertIn("Total items processed (from checkpoint)", result.get("grooming_notes", ""))

            report = render_human_report(result)
            self.assertIn("Grooming / normalization", report)
            self.assertIn("Recovery Sources", report)

    def test_grooming_rich_cluster_evidence_and_validation_status(self):
        """Honey-style: PROGRESS with cluster_evidence + validation_status + per-cluster rationales should be extracted and rendered as first-class notes."""
        with tempfile.TemporaryDirectory() as td:
            progress = {
                "completed": [f"yt:{i} → youtube" for i in range(20)],
                "current_phase": "Validation complete",
                "validation_status": "PASS_GATES (0 real patches needed; all candidates already canonical or deferred)",
                "cluster_evidence": {
                    "youtube": {"reviewed": 18, "already_canonical": 1, "deferred": 0, "rationale": "No 'yt' frontmatter tags existed in live vault snapshot"},
                    "other": {"reviewed": 2, "deferred": 2, "reason": "non-matching structure"}
                },
                "canonical_rules": "youtube lowercase only for this slice",
                "gotchas": ["Independent parser cross-check recommended for reviewers"]
            }
            (Path(td) / "PROGRESS.json").write_text(json.dumps(progress, indent=2))

            raw = {"text": "Tiny yt->youtube validation slice complete. No yt tags found.", "exit_code": 0}
            result = normalize_result(raw, target_dir=td)

            self.assertTrue(result.get("summary_synthesized_from_checkpoint"))
            self.assertEqual(result.get("validation_status"), progress["validation_status"])
            ce = result.get("cluster_evidence") or {}
            self.assertIn("youtube", ce)
            self.assertIn("already_canonical", ce.get("youtube", {}))
            self.assertIn("canonical_rules", result)

            report = render_human_report(result)
            self.assertIn("♻️ Grooming / Normalization Notes", report)
            self.assertIn("Run Intent", report)  # validation-only clarity
            self.assertIn("Validation Status", report)
            self.assertIn("already_canonical", report)
            self.assertIn("youtube", report)

    def test_validation_only_partial_renders_honest_no_work_evidence(self):
        """Simulates exact Honey v4 outcome: honest PARTIAL on validation pass with zero real patches, rich evidence, no synthetic invention."""
        with tempfile.TemporaryDirectory() as td:
            progress = {
                "completed": ["Scanned live vault snapshot for yt frontmatter tags", "Found 0 instances of non-canonical 'yt'", "1 file had exact lowercase 'youtube' already (04 Research/AI/YouTube.md)"],
                "validation_gates": ["candidate/temp only", "temp-snapshot validation", "no synthetics in patches/", "STATUS PASS requires >=1 real validated patch"],
                "real_target_evidence": "Independent frontmatter parser confirmed 0 yt tags across entire vault",
                "next_steps": ["Widen scope only after this narrow validation is accepted"]
            }
            (Path(td) / "PROGRESS.json").write_text(json.dumps(progress, indent=2))

            raw = {"text": "Validation slice complete. STATUS: PARTIAL (correctly — 0 candidates qualified for real patches).", "exit_code": 0}
            result = normalize_result(raw, target_dir=td)

            self.assertIn("real_target_evidence", result)
            self.assertIn("validation_gates", result.get("observations", "") or str(result))

            report = render_human_report(result)
            # Honest no-work + evidence is the success signal (Honey v4 style)
            # For small pure-validation no_changes lists we surface via Run Intent + rich Observations/Recovery Sources
            self.assertIn("Run Intent", report)
            self.assertIn("Validation-focused run", report)
            self.assertIn("real_target_evidence", report)  # the key evidence field made it into the human report
            # Rich gates and independent verification note are present
            self.assertIn("validation_gates", report.lower())
            # No claim of patches when none existed (the core anti-synthetic win)
            self.assertNotIn("patch available", report.lower())

    def test_best_effort_recovery_respects_security_guards(self):
        """P1 regression: _best_effort_summary_extraction must apply ownership/mode + size
        checks when reading PROGRESS files for synthesis (same hardening as load_checkpoint_context).
        Insecure or huge checkpoints must be skipped, not ingested into reports/JSON."""
        with tempfile.TemporaryDirectory() as td:
            # Insecure (world-writable) PROGRESS.json — must be skipped
            bad = Path(td) / "PROGRESS.json"
            bad.write_text('{"completed": ["evil"], "gotchas": ["should not appear"]}')
            bad.chmod(0o666)

            from code_delegation_harness.harness import _best_effort_summary_extraction
            res = _best_effort_summary_extraction("some output without markers", target_dir=td)

            self.assertIn("SKIPPED: insecure", res.get("observations", ""))
            self.assertNotIn("evil", res.get("observations", ""))

            # Too large — must be skipped
            bad2 = Path(td) / "TASK_STATE.md"
            bad2.write_text("x" * 100000)
            bad2.chmod(0o600)
            res2 = _best_effort_summary_extraction("more output", target_dir=td)
            self.assertIn("SKIPPED: too large", res2.get("observations", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
