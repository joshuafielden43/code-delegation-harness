"""Tests for the hygiene stanza system (stanzas/)."""
import unittest

from src.code_delegation_harness.stanzas import (
    STANZA_VERSION,
    assert_stanza_portable,
    load_stanza,
)


class TestStanzaVersion(unittest.TestCase):
    def test_version_is_v1(self):
        self.assertEqual(STANZA_VERSION, "v1.0")


class TestLoadStanza(unittest.TestCase):
    def test_base_module_loads(self):
        text = load_stanza(["base"])
        self.assertGreater(len(text), 50)

    def test_default_loads_base(self):
        text = load_stanza()
        self.assertGreater(len(text), 50)

    def test_none_defaults_to_base(self):
        text = load_stanza(None)
        self.assertGreater(len(text), 50)

    def test_unknown_module_silently_skipped(self):
        # Unknown modules should not raise — they're future extension slots
        text = load_stanza(["base", "nonexistent_module_xyz"])
        self.assertGreater(len(text), 50)

    def test_empty_list_returns_empty(self):
        text = load_stanza([])
        self.assertEqual(text, "")

    def test_stanza_content_is_generic(self):
        text = load_stanza(["base"])
        # The base stanza must not mention specific projects or tools
        lower = text.lower()
        for term in ("proxmox", "hermes", "gcdh", "harness.py"):
            self.assertNotIn(term, lower, f"Stanza mentions project-specific term: {term}")

    def test_stanza_covers_core_rules(self):
        text = load_stanza(["base"])
        # Core hygiene rules from PRD §3.5 must be present
        self.assertIn("auditable", text.lower())
        self.assertIn("interface", text.lower())
        self.assertIn("rewrite", text.lower())
        self.assertIn("decision", text.lower())
        self.assertIn("dependencies", text.lower())

    def test_stanza_is_appended_pattern(self):
        """Verify stanza can be appended to a prompt without corruption."""
        prompt = "TASK: Add a login feature\nTARGET: src/auth.py"
        stanza = load_stanza(["base"])
        combined = prompt + "\n\n--- ENGINEERING STANDARDS ---\n" + stanza
        self.assertIn("TASK:", combined)
        self.assertIn("auditable", combined.lower())


class TestAssertStanzaPortable(unittest.TestCase):
    def test_clean_stanza_passes(self):
        clean = "Produce auditable artifacts. Respect interface contracts."
        assert_stanza_portable(clean)  # should not raise

    def test_base_stanza_is_portable(self):
        stanza = load_stanza(["base"])
        assert_stanza_portable(stanza)  # base stanza must always pass

    def test_py_file_reference_fails(self):
        bad = "Always use the pattern from auth.py as the template."
        with self.assertRaises(ValueError):
            assert_stanza_portable(bad)

    def test_absolute_path_fails(self):
        bad = "Write output to /Users/jcf/projects/myapp/src/module.py."
        with self.assertRaises(ValueError):
            assert_stanza_portable(bad)

    def test_task_prefix_fails(self):
        bad = "TASK: Use the existing config file."
        with self.assertRaises(ValueError):
            assert_stanza_portable(bad)

    def test_sh_file_reference_fails(self):
        bad = "Run setup.sh before starting."
        with self.assertRaises(ValueError):
            assert_stanza_portable(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
