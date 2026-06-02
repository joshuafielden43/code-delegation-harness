#!/usr/bin/env python3
"""Public repository hygiene checks."""

from pathlib import Path
import re
import unittest


class TestPublicHygiene(unittest.TestCase):
    def test_public_tree_has_professional_language(self):
        root = Path(__file__).resolve().parent.parent
        banned_terms = [
            "fu" + "ck",
            "fu" + "cking",
            "sh" + "it",
            "bull" + ("sh" + "it"),
            "ass" + "hole",
            "bi" + "tch",
            "cu" + "nt",
            "di" + "ck",
            "pi" + "ss",
            "mother" + "fucker",
            "god" + ("da" + "mn"),
            "w" + "tf",
        ]
        banned = re.compile(r"\b(" + "|".join(re.escape(term) for term in banned_terms) + r")\b", re.IGNORECASE)
        skip_dirs = {
            ".git",
            ".pytest_cache",
            "__pycache__",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            ".venv",
            "venv",
        }
        text_suffixes = {
            ".cfg",
            ".ini",
            ".json",
            ".md",
            ".py",
            ".sh",
            ".toml",
            ".txt",
            ".yaml",
            ".yml",
        }
        offenders = []
        for path in root.rglob("*"):
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.name.lower() == "agents.md":
                offenders.append(f"{path.relative_to(root)}: AGENTS.md is not a public artifact")
                continue
            if not path.is_file() or path.suffix.lower() not in text_suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if banned.search(line):
                    offenders.append(f"{path.relative_to(root)}:{line_no}: {line.strip()}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
