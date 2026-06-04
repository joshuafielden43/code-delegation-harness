"""
Intake Gate — runs before every CLI invocation (D-01).

Single orchestrator call that performs four operations:
  1. Detection   — is this prompt already AI-structured, or human natural language?
  2. Normalization — if human, convert to structured prompt via orchestrator model
  3. Manifest extraction — pull expected artifacts as a typed list
  4. Attack frame pre-generation — produce the adversarial critique template upfront

The orchestrator model is the smartest available (D-02). It is always separate
from the execution CLI. Expensive thinking happens once at intake; execution is cheap.

If intake fails for any reason, the harness degrades gracefully: passes the raw
prompt through with a warning and marks was_normalized=False in the trace.
Never aborts the run.

Install optional extras for the Anthropic backend:
  pip install "code-delegation-harness[intake]"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Normalization prompt versioning (OQ-02)
# ---------------------------------------------------------------------------

NORMALIZATION_PROMPT_VERSION = "normalization-v1.0"
_PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_normalization_prompt(version: str = NORMALIZATION_PROMPT_VERSION) -> str:
    """Load the normalization system prompt from the versioned file."""
    filename = f"{version}.txt"
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    # Fallback: inline minimal prompt if file missing (shouldn't happen in installed package)
    return (
        "You are an intake normalizer. Given a raw coding task, produce:\n"
        "1. intent_normalized — structured, explicit rewrite\n"
        "2. manifest_expected — typed artifact list\n"
        "3. attack_frame_generated — adversarial critique template"
    )


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ArtifactExpectation:
    type: str = "file"         # file | function | class | interface | config | library
    name: str = ""
    description: str = ""


@dataclass
class IntakeResult:
    intent_detection: str = "human"        # human | ai_structured
    was_normalized: bool = False
    intent_normalized: str = ""            # always populated (passthrough or generated)
    manifest_expected: list = field(default_factory=list)   # List[ArtifactExpectation]
    attack_frame_generated: Optional[str] = None
    normalized_via_model: Optional[str] = None
    normalized_via_prompt_version: str = "normalization-v1.0"
    degraded: bool = False                 # True if orchestrator failed and we fell back
    degraded_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt detection (~5 lines of logic per PRD §3.2)
# ---------------------------------------------------------------------------

# Heuristics that signal AI-structured input (explicit fields, artifact refs,
# no conversational hedging). Not ML — a schema validator is sufficient.
_STRUCTURED_MARKERS = re.compile(
    r"(?:^|\n)\s*(?:TASK:|CONTEXT:|CONSTRAINTS:|TARGET:|WORKING DIRECTORY:|"
    r"FILES?:|FUNCTION:|CLASS:|INTERFACE:|ARTIFACT[S]?:)",
    re.IGNORECASE,
)
_HEDGING_PATTERN = re.compile(
    r"\b(I want|I'd like|could you|please|maybe|perhaps|I think|I need you to|"
    r"can you|would you|I'm trying|I was wondering)\b",
    re.IGNORECASE,
)


def detect_prompt_type(prompt: str) -> str:
    """Return 'ai_structured' if the prompt already satisfies the structured schema."""
    has_markers = bool(_STRUCTURED_MARKERS.search(prompt))
    has_hedging = bool(_HEDGING_PATTERN.search(prompt))
    has_artifacts = bool(re.search(r"\.(py|ts|js|go|rs|sh|yaml|yml|json|toml)\b", prompt))
    if has_markers and not has_hedging:
        return "ai_structured"
    if has_markers and has_artifacts and prompt.count("\n") >= 5:
        return "ai_structured"
    return "human"


# ---------------------------------------------------------------------------
# Orchestrator backends
# ---------------------------------------------------------------------------

class OrchestratorBackend(ABC):
    """Abstract base for orchestrator model calls."""

    @abstractmethod
    def run_intake(
        self,
        raw_prompt: str,
        model: str,
        timeout: int = 30,
    ) -> IntakeResult:
        ...


class AnthropicOrchestratorBackend(OrchestratorBackend):
    """
    Calls the Anthropic API directly using the anthropic SDK with native tool_use
    for structured output. No instructor dependency.

    Requires: pip install "code-delegation-harness[intake]"
    (only needs `anthropic`; instructor is no longer required)
    """

    # Tool schema for native tool_use structured output (OQ-04)
    _TOOL_SCHEMA = {
        "name": "intake_result",
        "description": "Structured intake normalization result",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent_normalized": {
                    "type": "string",
                    "description": (
                        "The task rewritten as a structured, explicit prompt. "
                        "Direct imperative form. No hedging language."
                    ),
                },
                "manifest_expected": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["file", "function", "class", "interface", "config", "library"]},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["type", "name", "description"],
                    },
                },
                "attack_frame_generated": {
                    "type": "string",
                    "description": (
                        "Pre-computed adversarial critique template. "
                        "Specific to this task: weakest assumptions, likely spec gaps, "
                        "skipped error paths, implicit dependencies."
                    ),
                },
            },
            "required": ["intent_normalized", "manifest_expected", "attack_frame_generated"],
        },
    }

    def run_intake(self, raw_prompt: str, model: str, timeout: int = 30) -> IntakeResult:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "Anthropic backend requires the [intake] extra: "
                "pip install 'code-delegation-harness[intake]'"
            )

        system_prompt = load_normalization_prompt(NORMALIZATION_PROMPT_VERSION)
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=[self._TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "intake_result"},
            messages=[{"role": "user", "content": f"RAW TASK:\n{raw_prompt}"}],
        )

        # Extract tool_use block
        tool_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            raise RuntimeError("Anthropic API did not return a tool_use block")

        data = tool_block.input
        return IntakeResult(
            intent_detection="human",
            was_normalized=True,
            intent_normalized=data.get("intent_normalized", raw_prompt),
            manifest_expected=[
                ArtifactExpectation(
                    type=a.get("type", "file"),
                    name=a.get("name", ""),
                    description=a.get("description", ""),
                )
                for a in (data.get("manifest_expected") or [])
                if isinstance(a, dict)
            ],
            attack_frame_generated=data.get("attack_frame_generated"),
            normalized_via_model=model,
            normalized_via_prompt_version=NORMALIZATION_PROMPT_VERSION,
        )


class CLIOrchestratorBackend(OrchestratorBackend):
    """
    Calls the same execution CLI for orchestration (no extra deps required).
    Uses a structured-output-requesting prompt and parses JSON from stdout.
    Accuracy is lower than the Anthropic backend but works offline.
    """

    def __init__(self, cli_name: str = "grok", extra_args: Optional[list] = None):
        self.cli_name = cli_name
        self.extra_args = extra_args or []

    def run_intake(self, raw_prompt: str, model: str, timeout: int = 30) -> IntakeResult:
        # Build intake prompt from versioned file + JSON output instruction
        normalization_system = load_normalization_prompt(NORMALIZATION_PROMPT_VERSION)
        intake_prompt = (
            f"{normalization_system}\n\n"
            "Respond ONLY with a JSON object (no prose, no markdown, no code fences) "
            "with exactly these keys:\n"
            '  "intent_normalized": string\n'
            '  "manifest_expected": array of {"type": string, "name": string, "description": string}\n'
            '  "attack_frame_generated": string\n\n'
            f"RAW TASK:\n{raw_prompt}"
        )

        cmd = [self.cli_name, "-p", intake_prompt, "-m", model,
               "--output-format", "json", "--max-turns", "5"] + self.extra_args
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            text = proc.stdout.strip()
            # Try to extract JSON from the CLI output (may be wrapped in a result envelope)
            data = _extract_json_from_cli_output(text)
            if data and all(k in data for k in ("intent_normalized", "manifest_expected")):
                return IntakeResult(
                    intent_detection="human",
                    was_normalized=True,
                    intent_normalized=data["intent_normalized"],
                    manifest_expected=[
                        ArtifactExpectation(
                            type=a.get("type", "file"),
                            name=a.get("name", ""),
                            description=a.get("description", ""),
                        )
                        for a in (data.get("manifest_expected") or [])
                        if isinstance(a, dict)
                    ],
                    attack_frame_generated=data.get("attack_frame_generated"),
                    normalized_via_model=model,
                    normalized_via_prompt_version=NORMALIZATION_PROMPT_VERSION,
                )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass
        return _degraded_intake(raw_prompt, "cli_orchestrator_failed")


def _extract_json_from_cli_output(text: str) -> Optional[dict]:
    """Extract the first valid JSON object from CLI output (may be wrapped in an envelope)."""
    # Try direct parse first; if it succeeds AND looks like an intake result, return it.
    # If it looks like a CLI envelope (has "text" or "content" key whose value is JSON), unwrap.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            # Check if this is already the intake result (has expected keys)
            if "intent_normalized" in parsed or "manifest_expected" in parsed:
                return parsed
            # Otherwise check for CLI envelope with a text/content field containing JSON
            inner_str = parsed.get("text") or parsed.get("content") or ""
            if inner_str and isinstance(inner_str, str):
                try:
                    inner = json.loads(inner_str)
                    if isinstance(inner, dict):
                        return inner
                except (json.JSONDecodeError, ValueError):
                    pass
            # Return whatever we got (let caller decide if keys are present)
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Try to find a JSON object embedded in prose
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_orchestrator(
    provider: str = "auto",
    cli_name: str = "grok",
    extra_cli_args: Optional[list] = None,
) -> OrchestratorBackend:
    """
    Return the appropriate orchestrator backend.

    provider:
      "auto"      — use Anthropic if ANTHROPIC_API_KEY is set, else CLI
      "anthropic" — always use Anthropic (raises if [intake] extras not installed)
      "cli"       — always use the execution CLI
    """
    if provider == "anthropic":
        return AnthropicOrchestratorBackend()
    if provider == "cli":
        return CLIOrchestratorBackend(cli_name=cli_name, extra_args=extra_cli_args)
    # auto
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicOrchestratorBackend()
    return CLIOrchestratorBackend(cli_name=cli_name, extra_args=extra_cli_args)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_intake_gate(
    raw_prompt: str,
    *,
    orchestrator: OrchestratorBackend,
    model: str,
    timeout: int = 30,
    quiet: bool = False,
) -> IntakeResult:
    """
    Run the intake gate. Always returns an IntakeResult.

    If the prompt is already AI-structured: passthrough (was_normalized=False).
    If human: normalize via orchestrator.
    On any failure: degrade gracefully, pass raw prompt through, set degraded=True.
    Never raises.
    """
    detection = detect_prompt_type(raw_prompt)

    if detection == "ai_structured":
        if not quiet:
            print("[cdh:intake] Prompt is AI-structured — skipping normalization (passthrough).")
        return IntakeResult(
            intent_detection="ai_structured",
            was_normalized=False,
            intent_normalized=raw_prompt,
        )

    if not quiet:
        print(f"[cdh:intake] Human prompt detected — normalizing via orchestrator ({model})...")

    try:
        result = orchestrator.run_intake(raw_prompt, model=model, timeout=timeout)
        result.intent_detection = "human"
        if not quiet and result.was_normalized:
            n = len(result.manifest_expected)
            print(f"[cdh:intake] Normalization complete. {n} artifact(s) in manifest.")
        return result
    except Exception as exc:
        if not quiet:
            print(f"[cdh:intake] WARNING: orchestrator failed ({exc}). Passing raw prompt through.")
        return _degraded_intake(raw_prompt, str(exc))


def _degraded_intake(raw_prompt: str, reason: str) -> IntakeResult:
    return IntakeResult(
        intent_detection="human",
        was_normalized=False,
        intent_normalized=raw_prompt,
        degraded=True,
        degraded_reason=reason[:300],
    )
