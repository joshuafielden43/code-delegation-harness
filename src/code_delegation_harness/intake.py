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
from typing import Optional


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
    Calls the Anthropic API directly using the anthropic SDK + instructor
    for structured output. Requires pip install "cdh[intake]".
    """

    def run_intake(self, raw_prompt: str, model: str, timeout: int = 30) -> IntakeResult:
        try:
            import anthropic
            import instructor
            from pydantic import BaseModel, Field

            class _Artifact(BaseModel):
                type: str = Field(default="file", description="file|function|class|interface|config|library")
                name: str
                description: str

            class _IntakeOutput(BaseModel):
                intent_normalized: str = Field(
                    description=(
                        "The user's intent rewritten as a structured, explicit prompt. "
                        "Include: task objective, working directory if mentioned, explicit "
                        "artifact list, constraints. Be precise — no hedging language."
                    )
                )
                manifest_expected: list[_Artifact] = Field(
                    default_factory=list,
                    description="Typed list of artifacts the task explicitly or implicitly requires.",
                )
                attack_frame_generated: str = Field(
                    description=(
                        "Pre-computed adversarial critique template for this task. "
                        "Written as an attack prompt: identify the weakest assumptions, "
                        "the most likely gaps in spec coverage, the error paths most likely "
                        "to be skipped, and any implicit dependencies. Be specific to this task."
                    )
                )

            client = instructor.from_anthropic(anthropic.Anthropic())
            result = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "You are an intake normalizer for a code delegation harness. "
                            "Given the user's raw coding task below, produce:\n"
                            "1. A structured, explicit normalized prompt\n"
                            "2. A typed manifest of expected artifacts\n"
                            "3. A pre-generated adversarial attack frame\n\n"
                            f"RAW TASK:\n{raw_prompt}"
                        ),
                    }
                ],
                response_model=_IntakeOutput,
            )
            return IntakeResult(
                intent_detection="human",
                was_normalized=True,
                intent_normalized=result.intent_normalized,
                manifest_expected=[
                    ArtifactExpectation(type=a.type, name=a.name, description=a.description)
                    for a in result.manifest_expected
                ],
                attack_frame_generated=result.attack_frame_generated,
                normalized_via_model=model,
            )
        except ImportError:
            raise RuntimeError(
                "Anthropic backend requires the [intake] extra: "
                "pip install 'code-delegation-harness[intake]'"
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
        intake_prompt = (
            "You are an intake normalizer. Given the user's raw coding task, "
            "respond ONLY with a JSON object (no prose, no markdown) with exactly these keys:\n"
            '  "intent_normalized": string — task rewritten as explicit structured prompt\n'
            '  "manifest_expected": array of {"type": string, "name": string, "description": string}\n'
            '  "attack_frame_generated": string — adversarial critique template for this task\n\n'
            f"RAW TASK:\n{raw_prompt}\n\n"
            "Respond with only the JSON object."
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
