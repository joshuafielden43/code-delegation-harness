"""
Hygiene stanza loader.

The hygiene stanza is a fixed, version-pinned block of universal good practice
appended to every normalized prompt before it reaches the execution CLI.

Hard rule (D-05): if the stanza mentions any specific project, file, script,
or path, it is not hygiene — it is context injection and does not belong here.
assert_stanza_portable() enforces this at load time.
"""
from __future__ import annotations

import re
from pathlib import Path

STANZA_VERSION = "v1.0"
_STANZA_DIR = Path(__file__).parent

# Plugin slot for future domain-specific modules (infrastructure, web, etc.).
# Nothing plugs in yet. Slot exists so Phase 6 requires no structural change.
_STANZA_FILES: dict[str, str] = {
    "base": str(_STANZA_DIR / "base_v1.0.txt"),
}

# Portability lint: patterns that indicate project-specific content.
# A stanza containing any of these is coupled to one workflow, not universal.
_PROJECT_SPECIFIC_PATTERNS = [
    re.compile(r"\b(proxmox|hermes|grok|codex|claude|agy)\b", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9_.-]+\.(py|sh|yaml|yml|json|toml|md)\b"),
    re.compile(r"[~/][A-Za-z0-9_./-]{5,}"),          # absolute or home-relative paths
    re.compile(r"(?:^|\s)(TASK:|CONTEXT:|INSTRUCTIONS:|WORKING DIRECTORY:)", re.MULTILINE),
]


def assert_stanza_portable(text: str) -> None:
    """Raise if the stanza contains project-specific references."""
    for pat in _PROJECT_SPECIFIC_PATTERNS:
        m = pat.search(text)
        if m:
            raise ValueError(
                f"Hygiene stanza portability violation: found '{m.group()}' "
                f"(matched pattern '{pat.pattern}'). "
                "A hygiene stanza must be generic and project-agnostic. "
                "Move project-specific content to --context or --constraints."
            )


def load_stanza(modules: list[str] | None = None) -> str:
    """Load and concatenate the requested stanza modules.

    Returns the combined stanza text. Each module is separated by a blank line.
    Unknown module names are silently skipped (future-proofing: a module that
    doesn't exist yet should not break existing invocations).
    """
    if modules is None:
        modules = ["base"]

    parts: list[str] = []
    for name in modules:
        path_str = _STANZA_FILES.get(name)
        if path_str is None:
            continue
        p = Path(path_str)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)

    return "\n\n".join(parts)
