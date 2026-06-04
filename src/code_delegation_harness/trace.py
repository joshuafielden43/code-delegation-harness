"""
Build Attempt Trace — canonical record of one harness invocation.

Every gcdh run produces a trace written to {research_dir}/build-attempts/.
The schema tracks the full lifecycle: raw intent → normalization → manifest →
runs with SHA-256 output digests → attack critique → verdict.

Phase 1 populates the run/attack/verdict sections. Intake/confirmation/manifest
sections are null-populated until Phase 2/3/4 are wired. No schema migration
needed when later phases fill them in.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _trace_id() -> str:
    """Sortable trace ID: YYYYMMDDTHHMMSSmmm-<8hex>."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:18]
    rand = os.urandom(4).hex()
    return f"{ts}-{rand}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

@dataclass
class NormalizedVia:
    model: Optional[str] = None
    prompt_version: Optional[str] = None


@dataclass
class ConfirmationCorrection:
    raw_correction: str = ""
    updated_normalized: str = ""


@dataclass
class ConfirmationBlock:
    shown_to_user: bool = False
    iterations: int = 0
    corrections: list = field(default_factory=list)  # List[ConfirmationCorrection]


@dataclass
class ArtifactExpectation:
    type: str = "file"          # file | function | class | interface | config | library
    name: str = ""
    description: str = ""


@dataclass
class ManifestBlock:
    expected: list = field(default_factory=list)   # List[ArtifactExpectation]
    found: list = field(default_factory=list)       # List[str]
    missing: list = field(default_factory=list)     # List[str]


@dataclass
class RunRecord:
    run_id: int = 1
    prompt_chars: int = 0
    cli: str = ""
    cli_args: list = field(default_factory=list)
    exit: str = "clean"                   # clean | fail | timeout
    stdout_digest: Optional[str] = None   # SHA-256 of full stdout
    stderr_digest: Optional[str] = None   # SHA-256 of full stderr
    stdout_path: Optional[str] = None     # path in research/tmp
    stderr_path: Optional[str] = None     # path in research/tmp
    codebase_diff: Optional[str] = None   # path to diff artifact
    attack_triggered: bool = False


@dataclass
class CritiqueItem:
    assumption: str = ""
    category: str = "scope"   # spec_coverage | interface_contract | error_path | scope | implicit_dependency
    severity: str = "medium"  # low | medium | high


@dataclass
class AttackBlock:
    generator: Optional[str] = None       # success | failure
    critique: list = field(default_factory=list)   # List[CritiqueItem]
    manifest_gaps_injected: list = field(default_factory=list)
    prompt_generated: Optional[str] = None
    attack_frame_from_intake: Optional[str] = None


@dataclass
class VerdictBlock:
    outcome: str = "failed"               # passed | failed | promoted
    smoke_tier: Optional[str] = None      # null | t1_exists | t2_compiles | t3_interface
    notes: str = ""
    tags: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Root trace
# ---------------------------------------------------------------------------

@dataclass
class BuildAttemptTrace:
    # Identity
    id: str = field(default_factory=_trace_id)
    status: str = "complete"   # complete | failed | abandoned | needs-review
    created: str = field(default_factory=_now_iso)

    # Intent
    intent_raw: str = ""
    intent_detection: Optional[str] = None       # human | ai_structured | None if skipped
    was_normalized: bool = False
    intent_normalized: str = ""
    normalized_via: NormalizedVia = field(default_factory=NormalizedVia)

    # Intake
    hygiene_stanza_version: Optional[str] = None
    stanza_modules: list = field(default_factory=list)
    attack_frame_generated: Optional[str] = None

    # Confirmation (null until Phase 4)
    confirmation: ConfirmationBlock = field(default_factory=ConfirmationBlock)

    # Manifest (null until Phase 2)
    manifest: ManifestBlock = field(default_factory=ManifestBlock)

    # Runs
    runs: list = field(default_factory=list)      # List[RunRecord]

    # Attack
    attack: AttackBlock = field(default_factory=AttackBlock)

    # Verdict
    verdict: VerdictBlock = field(default_factory=VerdictBlock)

    # Harness metadata
    harness_version: Optional[str] = None
    run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _to_dict_clean(obj) -> object:
    """Recursively convert dataclasses to dicts, dropping None-only leaves."""
    if isinstance(obj, (BuildAttemptTrace, NormalizedVia, ConfirmationBlock,
                        ManifestBlock, RunRecord, CritiqueItem, AttackBlock,
                        VerdictBlock, ArtifactExpectation, ConfirmationCorrection)):
        return {k: _to_dict_clean(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict_clean(i) for i in obj]
    return obj


def trace_to_yaml(trace: BuildAttemptTrace) -> str:
    """Minimal YAML serialisation (no PyYAML dep — hand-rolled for simple schema)."""
    d = _to_dict_clean(trace)
    return _dict_to_yaml(d, indent=0)


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Quote if contains special chars or looks like a YAML keyword
    needs_quote = any(c in s for c in (':', '#', '{', '}', '[', ']', ',', '&', '*',
                                        '?', '|', '-', '<', '>', '=', '!', '%', '@', '`'))
    needs_quote = needs_quote or s in ("true", "false", "null", "yes", "no", "~")
    needs_quote = needs_quote or "\n" in s
    if needs_quote or not s:
        if "\n" in s:
            lines = s.splitlines()
            return "|\n" + "\n".join("  " + l for l in lines)
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _dict_to_yaml(d, indent: int) -> str:
    pad = "  " * indent
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            if not v:
                lines.append(f"{pad}{k}: {{}}")
            else:
                lines.append(f"{pad}{k}:")
                lines.append(_dict_to_yaml(v, indent + 1))
        elif isinstance(v, list):
            if not v:
                lines.append(f"{pad}{k}: []")
            else:
                lines.append(f"{pad}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        first = True
                        for ik, iv in item.items():
                            prefix = f"{pad}  - " if first else f"{pad}    "
                            first = False
                            if isinstance(iv, (dict, list)):
                                lines.append(f"{prefix}{ik}:")
                            else:
                                lines.append(f"{prefix}{ik}: {_yaml_scalar(iv)}")
                    else:
                        lines.append(f"{pad}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{pad}{k}: {_yaml_scalar(v)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Research/tmp helpers
# ---------------------------------------------------------------------------

def ensure_research_dir(research_dir: str) -> Path:
    p = Path(research_dir)
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    (p / "build-attempts").mkdir(exist_ok=True, mode=0o700)
    return p


def write_output_to_research(research_dir: str, run_id: str, label: str, content: str) -> tuple[str, str]:
    """Write stdout or stderr to research/tmp, return (path, sha256)."""
    p = ensure_research_dir(research_dir)
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "output"
    out_path = p / f"{run_id}-{safe_label}.txt"
    data = content.encode("utf-8", errors="replace")
    out_path.write_bytes(data)
    out_path.chmod(0o600)
    return str(out_path), _sha256_bytes(data)


def write_trace(trace: BuildAttemptTrace, research_dir: str) -> str:
    """Write the trace as YAML to research/tmp/build-attempts/. Returns path."""
    p = ensure_research_dir(research_dir)
    trace_path = p / "build-attempts" / f"{trace.id}.yaml"
    yaml_text = f"---\n# Build Attempt Trace\n# id: {trace.id}\n\n{trace_to_yaml(trace)}\n"
    trace_path.write_text(yaml_text, encoding="utf-8")
    trace_path.chmod(0o600)
    return str(trace_path)


def build_trace_from_result(
    *,
    intent_raw: str,
    intent_normalized: str,
    was_normalized: bool,
    intent_detection: Optional[str],
    normalized_via: Optional[NormalizedVia],
    run_records: list,        # List[RunRecord]
    attack_block: AttackBlock,
    verdict: VerdictBlock,
    manifest: Optional[ManifestBlock] = None,
    confirmation: Optional[ConfirmationBlock] = None,
    hygiene_stanza_version: Optional[str] = None,
    stanza_modules: Optional[list] = None,
    attack_frame_generated: Optional[str] = None,
    run_id: Optional[str] = None,
    harness_version: Optional[str] = None,
    status: str = "complete",
) -> BuildAttemptTrace:
    return BuildAttemptTrace(
        status=status,
        intent_raw=intent_raw,
        intent_detection=intent_detection,
        was_normalized=was_normalized,
        intent_normalized=intent_normalized,
        normalized_via=normalized_via or NormalizedVia(),
        hygiene_stanza_version=hygiene_stanza_version,
        stanza_modules=stanza_modules or [],
        attack_frame_generated=attack_frame_generated,
        confirmation=confirmation or ConfirmationBlock(),
        manifest=manifest or ManifestBlock(),
        runs=run_records,
        attack=attack_block,
        verdict=verdict,
        run_id=run_id,
        harness_version=harness_version,
    )
