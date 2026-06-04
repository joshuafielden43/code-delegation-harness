"""Tests for the build attempt trace schema (trace.py)."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from src.code_delegation_harness.trace import (
    AttackBlock,
    BuildAttemptTrace,
    ConfirmationBlock,
    ConfirmationCorrection,
    CritiqueItem,
    ManifestBlock,
    ArtifactExpectation,
    NormalizedVia,
    RunRecord,
    VerdictBlock,
    _sha256_bytes,
    build_trace_from_result,
    ensure_research_dir,
    write_output_to_research,
    write_trace,
)


class TestSha256Helper(unittest.TestCase):
    def test_known_hash(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        self.assertEqual(_sha256_bytes(data), expected)

    def test_empty_bytes(self):
        h = _sha256_bytes(b"")
        self.assertEqual(len(h), 64)


class TestEnsureResearchDir(unittest.TestCase):
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as d:
            research = os.path.join(d, "research", "tmp")
            p = ensure_research_dir(research)
            self.assertTrue(p.exists())
            self.assertTrue((p / "build-attempts").exists())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            research = os.path.join(d, "research", "tmp")
            ensure_research_dir(research)
            ensure_research_dir(research)  # should not raise


class TestEnsureResearchDirPermFix(unittest.TestCase):
    """D-02 (MoM): ensure_research_dir fixes permissions on pre-existing dirs."""

    def test_fixes_loose_permissions_on_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            research = os.path.join(d, "research", "tmp")
            ensure_research_dir(research)
            # Manually loosen permissions to simulate bad state
            os.chmod(research, 0o777)
            # Second call should fix them back to 0o700
            ensure_research_dir(research)
            mode = oct(os.stat(research).st_mode)
            self.assertIn("700", mode)


class TestWriteOutputToResearch(unittest.TestCase):
    def test_writes_file_and_returns_digest(self):
        with tempfile.TemporaryDirectory() as d:
            path, digest = write_output_to_research(d, "run123", "pass1-stdout", "hello output")
            self.assertTrue(os.path.exists(path))
            self.assertEqual(len(digest), 64)  # SHA-256 hex
            content = open(path).read()
            self.assertEqual(content, "hello output")

    def test_file_permissions_restrictive(self):
        with tempfile.TemporaryDirectory() as d:
            path, _ = write_output_to_research(d, "run123", "pass1-stdout", "data")
            mode = oct(os.stat(path).st_mode)
            self.assertIn("600", mode)


class TestWriteTrace(unittest.TestCase):
    def _make_minimal_trace(self) -> BuildAttemptTrace:
        return build_trace_from_result(
            intent_raw="add a login feature",
            intent_normalized="TASK: Add OAuth2 login to src/auth.py",
            was_normalized=True,
            intent_detection="human",
            normalized_via=NormalizedVia(model="claude-opus-4-8", prompt_version="normalization-v1.0"),
            run_records=[
                RunRecord(
                    run_id=1,
                    cli="grok-build",
                    exit="clean",
                    stdout_digest="deadbeef" * 8,
                    prompt_chars=1200,
                )
            ],
            attack_block=AttackBlock(
                generator="success",
                critique=[
                    CritiqueItem(
                        assumption="Happy path only — no error handling for failed token refresh",
                        category="error_path",
                        severity="medium",
                    )
                ],
            ),
            verdict=VerdictBlock(outcome="passed"),
            hygiene_stanza_version="v1.0",
            stanza_modules=["base"],
            run_id="abc12345",
        )

    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as d:
            trace = self._make_minimal_trace()
            path = write_trace(trace, d)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith(".yaml"))

    def test_trace_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as d:
            trace = self._make_minimal_trace()
            path = write_trace(trace, d)
            content = open(path).read()
            self.assertIn("intent_raw", content)
            self.assertIn("intent_normalized", content)
            self.assertIn("was_normalized", content)
            self.assertIn("stdout_digest", content)
            self.assertIn("error_path", content)
            self.assertIn("passed", content)
            self.assertIn("v1.0", content)

    def test_trace_id_format(self):
        """Trace IDs are timestamp-prefixed (sortable by creation time)."""
        import re as _re
        t = BuildAttemptTrace()
        # Format: YYYYMMDDTHHMMSSmmm-<8hex>
        self.assertRegex(t.id, r"^\d{8}T\d{9}-[0-9a-f]{8}$")

    def test_trace_ids_are_unique(self):
        ids = {BuildAttemptTrace().id for _ in range(20)}
        # At least some uniqueness from the random suffix
        self.assertGreater(len(ids), 1)

    def test_null_sections_serialise_cleanly(self):
        """Phase 1: manifest/confirmation null-populated — should not crash."""
        with tempfile.TemporaryDirectory() as d:
            trace = build_trace_from_result(
                intent_raw="task",
                intent_normalized="task",
                was_normalized=False,
                intent_detection=None,
                normalized_via=None,
                run_records=[],
                attack_block=AttackBlock(),
                verdict=VerdictBlock(),
            )
            path = write_trace(trace, d)
            self.assertTrue(os.path.exists(path))

    def test_file_permissions_restrictive(self):
        with tempfile.TemporaryDirectory() as d:
            trace = self._make_minimal_trace()
            path = write_trace(trace, d)
            mode = oct(os.stat(path).st_mode)
            self.assertIn("600", mode)

    def test_manifest_block_tracks_missing(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = ManifestBlock(
                expected=[ArtifactExpectation(type="file", name="auth.py", description="OAuth2 handler")],
                found=[],
                missing=["auth.py"],
            )
            trace = build_trace_from_result(
                intent_raw="task",
                intent_normalized="task",
                was_normalized=False,
                intent_detection="human",
                normalized_via=None,
                run_records=[],
                attack_block=AttackBlock(manifest_gaps_injected=["auth.py"]),
                verdict=VerdictBlock(),
                manifest=manifest,
            )
            path = write_trace(trace, d)
            content = open(path).read()
            self.assertIn("auth.py", content)
            self.assertIn("missing", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
