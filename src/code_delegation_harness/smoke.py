"""
Smoke testing and manifest diffing.

Phase 5 of the PRD: post-run verification that closes the loop between
what the intake gate said should be produced and what actually was.

Manifest diffing:
  After each CLI run, scan the target directory against manifest.expected
  to produce manifest.found and manifest.missing. These feed directly into
  the attack prompt — ground-truth gap targeting, not LLM inference.

Smoke test tiers (all auto-runnable):
  T1 — Artifact existence: is the file/module present on disk?
  T2 — Parse/compile/import: does `python -c 'import foo'` exit 0?
  T3 — Interface conformance: does the public API match the spec signature?
  T4 — Behavioural smoke: out of scope (human gate / separate test suite).
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Manifest diffing
# ---------------------------------------------------------------------------

def scan_for_artifact(artifact_name: str, target_dir: str) -> Optional[str]:
    """
    Look for an artifact by name in the target directory.
    Returns the relative path if found, None otherwise.

    Tries: exact name, name as module path (dots → slashes), common suffixes.
    """
    root = Path(target_dir)

    # Direct filename match
    for p in root.rglob(artifact_name):
        return str(p.relative_to(root))

    # Module-style name: auth.handler → auth/handler.py
    module_path = artifact_name.replace(".", "/")
    for suffix in (".py", ".ts", ".js", ".go", ".rs", ""):
        candidate = root / (module_path + suffix)
        if candidate.exists():
            return str(candidate.relative_to(root))

    # Basename match (ignore parent directories)
    base = Path(artifact_name).name
    for p in root.rglob(base):
        if not any(part.startswith(".") for part in p.parts):
            return str(p.relative_to(root))

    return None


def diff_manifest(expected: list, target_dir: str) -> tuple[list[str], list[str]]:
    """
    Compare expected artifacts against the actual target directory.

    Returns (found, missing) — both as lists of artifact names.
    expected: list of ArtifactExpectation (or any object with a .name attribute)
    """
    found: list[str] = []
    missing: list[str] = []

    for artifact in expected:
        name = artifact.name if hasattr(artifact, "name") else str(artifact)
        if not name:
            continue
        location = scan_for_artifact(name, target_dir)
        if location:
            found.append(name)
        else:
            missing.append(name)

    return found, missing


# ---------------------------------------------------------------------------
# Smoke test tiers
# ---------------------------------------------------------------------------

SMOKE_TIER_NULL = None
SMOKE_TIER_T1 = "t1_exists"
SMOKE_TIER_T2 = "t2_compiles"
SMOKE_TIER_T3 = "t3_interface"


class SmokeResult:
    """Result of running smoke tests against a set of artifacts."""

    def __init__(self):
        self.tier: Optional[str] = None          # highest tier passed
        self.t1_passed: list[str] = []
        self.t1_failed: list[str] = []
        self.t2_passed: list[str] = []
        self.t2_failed: list[str] = []
        self.t3_passed: list[str] = []
        self.t3_failed: list[str] = []
        self.notes: list[str] = []

    def to_dict(self) -> dict:
        return {
            "smoke_tier": self.tier,
            "t1": {"passed": self.t1_passed, "failed": self.t1_failed},
            "t2": {"passed": self.t2_passed, "failed": self.t2_failed},
            "t3": {"passed": self.t3_passed, "failed": self.t3_failed},
            "notes": self.notes,
        }


def run_t1(artifact_names: list[str], target_dir: str) -> tuple[list[str], list[str]]:
    """T1: artifact existence check. Returns (passed, failed)."""
    passed, failed = [], []
    for name in artifact_names:
        if scan_for_artifact(name, target_dir):
            passed.append(name)
        else:
            failed.append(name)
    return passed, failed


def run_t2(artifact_names: list[str], target_dir: str) -> tuple[list[str], list[str]]:
    """
    T2: parse/compile/import check.
    For .py files: `python -c 'import <module>'` exits 0.
    For other files: attempt AST parse (py) or syntax check where possible.
    """
    passed, failed = [], []
    root = Path(target_dir)

    for name in artifact_names:
        location = scan_for_artifact(name, target_dir)
        if not location:
            failed.append(name)
            continue

        path = root / location
        suffix = path.suffix.lower()

        if suffix == ".py":
            # Derive importable module name from path relative to target_dir
            try:
                rel = path.relative_to(root)
                parts = list(rel.with_suffix("").parts)
                module = ".".join(parts)
                result = subprocess.run(
                    [sys.executable, "-c", f"import sys; sys.path.insert(0, '{target_dir}'); import {module}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=target_dir,
                )
                if result.returncode == 0:
                    passed.append(name)
                else:
                    failed.append(name)
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, OSError):
                failed.append(name)
        else:
            # Non-Python: T2 is existence-equivalent (no compile check available)
            passed.append(name)

    return passed, failed


def run_t3(
    artifact_names: list[str],
    expected: list,
    target_dir: str,
) -> tuple[list[str], list[str]]:
    """
    T3: interface conformance check.
    For each expected artifact that has a description containing a function/class
    signature, compare against the AST of the found file.

    Currently checks: public functions/classes named in the description exist in
    the artifact's AST. Full signature matching is aspirational (Phase 5 scope).
    """
    passed, failed = [], []
    root = Path(target_dir)

    # Build a map from artifact name → expected description (for spec extraction)
    spec_map: dict[str, str] = {}
    for art in expected:
        n = art.name if hasattr(art, "name") else str(art)
        d = art.description if hasattr(art, "description") else ""
        spec_map[n] = d

    for name in artifact_names:
        location = scan_for_artifact(name, target_dir)
        if not location:
            failed.append(name)
            continue

        path = root / location
        if path.suffix.lower() != ".py":
            # T3 only defined for Python artifacts currently
            passed.append(name)
            continue

        description = spec_map.get(name, "")
        if not description:
            # No spec to check against — pass by convention
            passed.append(name)
            continue

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            failed.append(name)
            continue

        # Extract top-level names from AST
        top_level_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and isinstance(getattr(node, "col_offset", 1), int)
            and node.col_offset == 0
        }

        # Extract expected names from the description (simple heuristic: PascalCase or snake_case words)
        import re
        mentioned = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", description))
        # Filter to things that look like identifiers we'd expect to find
        expected_names = {
            n for n in mentioned
            if len(n) > 2 and not n.lower() in
               {"the", "and", "for", "that", "this", "with", "from", "into", "its",
                "file", "class", "function", "module", "returns", "handles", "should"}
        }

        if not expected_names:
            passed.append(name)
            continue

        # Check that at least one of the expected names appears in the artifact
        if expected_names & top_level_names:
            passed.append(name)
        else:
            failed.append(name)

    return passed, failed


def run_smoke_tests(
    expected: list,
    found_names: list[str],
    target_dir: str,
    tiers: tuple[bool, bool, bool] = (True, True, True),
) -> SmokeResult:
    """
    Run T1/T2/T3 smoke tests against found artifacts.

    tiers: (run_t1, run_t2, run_t3) — control which tiers execute.
    Returns SmokeResult with the highest tier passed.
    """
    result = SmokeResult()
    run_t1_flag, run_t2_flag, run_t3_flag = tiers

    if run_t1_flag and found_names:
        result.t1_passed, result.t1_failed = run_t1(found_names, target_dir)
        if result.t1_passed:
            result.tier = SMOKE_TIER_T1

    t2_candidates = result.t1_passed if run_t1_flag else found_names
    if run_t2_flag and t2_candidates:
        result.t2_passed, result.t2_failed = run_t2(t2_candidates, target_dir)
        if result.t2_passed:
            result.tier = SMOKE_TIER_T2

    t3_candidates = result.t2_passed if run_t2_flag else t2_candidates
    if run_t3_flag and t3_candidates:
        result.t3_passed, result.t3_failed = run_t3(t3_candidates, expected, target_dir)
        if result.t3_passed:
            result.tier = SMOKE_TIER_T3

    return result
