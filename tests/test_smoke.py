"""Tests for smoke testing tiers and manifest diffing (smoke.py)."""
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


class _Artifact:
    """Minimal stand-in for ArtifactExpectation in tests."""
    def __init__(self, name: str, type: str = "file", description: str = ""):
        self.name = name
        self.type = type
        self.description = description


class TestScanForArtifact(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import scan_for_artifact
        self.scan = scan_for_artifact

    def test_finds_exact_filename(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.py").write_text("# auth")
            self.assertIsNotNone(self.scan("auth.py", d))

    def test_finds_in_subdirectory(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "src"
            sub.mkdir()
            (sub / "handler.py").write_text("# h")
            self.assertIsNotNone(self.scan("handler.py", d))

    def test_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.scan("missing_thing.py", d))

    def test_finds_module_style_name(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / "auth"
            pkg.mkdir()
            (pkg / "handler.py").write_text("# h")
            # "auth.handler" should resolve to auth/handler.py
            result = self.scan("auth.handler", d)
            self.assertIsNotNone(result)

    def test_returns_relative_path(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "foo.py").write_text("x")
            result = self.scan("foo.py", d)
            self.assertFalse(result.startswith("/"))


class TestDiffManifest(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import diff_manifest
        self.diff = diff_manifest

    def test_all_found(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("x")
            (Path(d) / "b.py").write_text("x")
            arts = [_Artifact("a.py"), _Artifact("b.py")]
            found, missing = self.diff(arts, d)
            self.assertEqual(sorted(found), ["a.py", "b.py"])
            self.assertEqual(missing, [])

    def test_some_missing(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "present.py").write_text("x")
            arts = [_Artifact("present.py"), _Artifact("absent.py")]
            found, missing = self.diff(arts, d)
            self.assertIn("present.py", found)
            self.assertIn("absent.py", missing)

    def test_all_missing(self):
        with tempfile.TemporaryDirectory() as d:
            arts = [_Artifact("x.py"), _Artifact("y.py")]
            found, missing = self.diff(arts, d)
            self.assertEqual(found, [])
            self.assertEqual(sorted(missing), ["x.py", "y.py"])

    def test_empty_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            found, missing = self.diff([], d)
            self.assertEqual(found, [])
            self.assertEqual(missing, [])


class TestRunT1(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import run_t1
        self.run = run_t1

    def test_passes_for_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "thing.py").write_text("x")
            passed, failed = self.run(["thing.py"], d)
            self.assertIn("thing.py", passed)
            self.assertEqual(failed, [])

    def test_fails_for_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            passed, failed = self.run(["nope.py"], d)
            self.assertEqual(passed, [])
            self.assertIn("nope.py", failed)


class TestRunT2(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import run_t2
        self.run = run_t2

    def test_passes_for_importable_module(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mymod.py").write_text("x = 1\n")
            passed, failed = self.run(["mymod.py"], d)
            self.assertIn("mymod.py", passed)

    def test_fails_for_syntax_error(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.py").write_text("def foo(\n")
            passed, failed = self.run(["broken.py"], d)
            self.assertIn("broken.py", failed)

    def test_non_python_passes_t2(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.yaml").write_text("key: value\n")
            passed, failed = self.run(["config.yaml"], d)
            self.assertIn("config.yaml", passed)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            passed, failed = self.run(["ghost.py"], d)
            self.assertIn("ghost.py", failed)


class TestRunT3(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import run_t3
        self.run = run_t3

    def test_passes_when_expected_name_present(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.py").write_text(
                "class OAuthHandler:\n    pass\n"
            )
            arts = [_Artifact("auth.py", description="OAuthHandler for OAuth2 login")]
            passed, failed = self.run(["auth.py"], arts, d)
            self.assertIn("auth.py", passed)

    def test_fails_when_expected_name_absent(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.py").write_text(
                "# empty module\n"
            )
            arts = [_Artifact("auth.py", description="OAuthHandler for OAuth2 login")]
            passed, failed = self.run(["auth.py"], arts, d)
            self.assertIn("auth.py", failed)

    def test_passes_with_no_description(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "utils.py").write_text("x = 1\n")
            arts = [_Artifact("utils.py", description="")]
            passed, failed = self.run(["utils.py"], arts, d)
            self.assertIn("utils.py", passed)

    def test_non_python_passes_t3(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "schema.json").write_text("{}")
            arts = [_Artifact("schema.json", description="JSON schema definition")]
            passed, failed = self.run(["schema.json"], arts, d)
            self.assertIn("schema.json", passed)


class TestRunSmokeTests(unittest.TestCase):
    def setUp(self):
        from src.code_delegation_harness.smoke import run_smoke_tests, SMOKE_TIER_T1, SMOKE_TIER_T2, SMOKE_TIER_T3
        self.run = run_smoke_tests
        self.T1 = SMOKE_TIER_T1
        self.T2 = SMOKE_TIER_T2
        self.T3 = SMOKE_TIER_T3

    def test_empty_found_returns_null_tier(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run(expected=[], found_names=[], target_dir=d)
            self.assertIsNone(result.tier)

    def test_reaches_t1_for_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "foo.py").write_text("x = 1\n")
            arts = [_Artifact("foo.py")]
            result = self.run(expected=arts, found_names=["foo.py"], target_dir=d)
            self.assertIsNotNone(result.tier)
            self.assertIn(result.tier, [self.T1, self.T2, self.T3])

    def test_reaches_t2_for_importable_module(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "clean.py").write_text("x = 1\n")
            arts = [_Artifact("clean.py")]
            result = self.run(expected=arts, found_names=["clean.py"], target_dir=d)
            self.assertIn(result.tier, [self.T2, self.T3])

    def test_result_has_summary_dict(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("x = 1\n")
            result = self.run(expected=[_Artifact("m.py")], found_names=["m.py"], target_dir=d)
            d_out = result.to_dict()
            self.assertIn("smoke_tier", d_out)
            self.assertIn("t1", d_out)
            self.assertIn("t2", d_out)
            self.assertIn("t3", d_out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
