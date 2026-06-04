# Architecture Overview

This document describes how the Code Delegation Harness is structured at a high level.

## Core Modules

### `harness.py` — Orchestration core

The heart of the system. Drives the full delegation lifecycle:

- `build_execution_prompt()` — builds the execution prompt (injected with normalised intent + manifest + hygiene stanza)
- `call_model_headless()` — thin CLI adapter; writes stdout/stderr to `research/tmp`, returns SHA-256 digests
- `_wait_for_background_completion()` — resilient polling loop for long-running tasks with dynamic PROGRESS.json injection
- `normalize_result()` — converts raw CLI output to structured result dict
- `render_human_report()` — produces the `.report.md` artifact
- `_compose_remediation_prompt()` — targeted inversion overlay for pass-2 attack loop
- `_run_confirmation_loop()` — opt-in pre-run confirmation with correction capture

### `intake.py` — Intake gate (Phase 2)

Runs before every CLI invocation (D-01). Single orchestrator call doing four things:

1. **Detection** — `detect_prompt_type()`: ~5-line schema validator (human vs AI-structured)
2. **Normalisation** — converts human prompts to structured form via orchestrator model
3. **Manifest extraction** — typed artifact list (`ArtifactExpectation`)
4. **Attack frame pre-generation** — adversarial critique template produced upfront

Backends:
- `AnthropicOrchestratorBackend` — Anthropic SDK, native `tool_use`, no `instructor` dep
- `CLIOrchestratorBackend` — execution CLI subprocess fallback, zero extra deps
- `get_orchestrator(provider="auto")` — auto-selects based on `ANTHROPIC_API_KEY`

Graceful degradation: any failure passes raw prompt through (`degraded=True`). Wrapped in `RetryPolicy(max=3)`.

### `trace.py` — Build attempt trace schema

Every invocation writes a YAML trace to `{research-dir}/build-attempts/{id}.yaml` (0600).

Schema sections:
- **intent** — raw, detection result, normalised, `normalized_via` (model + prompt version)
- **intake** — hygiene stanza version, stanza modules, pre-generated attack frame
- **confirmation** — whether shown to user, correction rounds, corrections list
- **manifest** — expected artifacts, found (filesystem scan), missing
- **runs** — per-pass records with CLI args, exit status, stdout/stderr SHA-256 digests, diff paths
- **attack** — generator type (success/failure), critique items, manifest gaps injected, prompt
- **verdict** — outcome, smoke tier, notes, tags

`write_output_to_research()` — routes full stdout/stderr to `research/tmp`, returns digest.
`prune_research_dir()` — age-based cleanup; mirrors `--prune` for status files.

### `smoke.py` — Manifest diffing + smoke testing (Phase 5)

Post-execution verification that closes the loop between what intake said should exist and what does.

- `diff_manifest(expected, target_dir)` — filesystem scan vs `manifest.expected` → `(found, missing)`
- `run_t1()` — artifact existence check
- `run_t2()` — `python -c 'import <module>'` exit 0 for Python artifacts
- `run_t3()` — AST check: public names from spec description present in artifact
- `run_smoke_tests()` — chains T1→T2→T3, returns `SmokeResult` with `verdict.smoke_tier`

Missing artifacts from `diff_manifest` are injected into the attack prompt as explicit `spec_coverage` weakness items.

### `stanzas/` — Hygiene stanza system (Phase 3)

- `base_v1.0.txt` — generic, portable, project-agnostic engineering standards
- `load_stanza(modules)` — loads and concatenates stanza modules
- `assert_stanza_portable(text)` — portability lint; fails if stanza references project-specific content
- Plugin slot (`_STANZA_FILES`) for future domain-specific modules (Phase 6)

### `prompts/` — Versioned orchestrator prompts (OQ-02)

- `normalization_v1.0.txt` — the intake system prompt as a versioned file
- `NORMALIZATION_PROMPT_VERSION` constant; recorded in every trace under `normalized_via.prompt_version`
- Edit the file to improve normalisation quality without touching Python source

### `status.py` — Run lifecycle management

Centralised, resilient handling of `.cdh-run-*.status` files:
- `StatusManager` — atomic 0600 writes, self-healing recovery, heartbeat, crash sentinels
- `register_crash_protection()` — atexit + signal handlers for clean crash marking

## Data Flow

```
User invokes gcdh --task "..." --target-dir /path [--auto-remediate] [--confirm]
    │
    ▼
[Intake Gate]  detect_prompt_type()
               ├─ ai_structured → passthrough
               └─ human → orchestrator call (normalise + manifest + attack frame)
    │
    ▼
[Confirmation Loop]  optional (--confirm)
               show intent + manifest → accept/correct → max 2 rounds
    │
    ▼
[Stanza Injection]  load_stanza() + manifest list appended to normalised prompt
    │
    ▼
[build_execution_prompt()]  wraps effective_task in full execution prompt
    │
    ▼
[call_model_headless()]  invokes CLI subprocess
               stdout/stderr → research/tmp (0600)
               SHA-256 digests → result dict
    │
    ├─ timed_out + --wait-for-completion → polling loop (dynamic PROGRESS.json injection)
    │
    ▼
[normalize_result()]  parse === DELEGATION SUMMARY === or synthesise from checkpoints
    │
    ▼
[diff_manifest() + run_smoke_tests()]  filesystem scan → found/missing, T1/T2/T3
               missing artifacts → injected into attack prompt weakness profile
    │
    ├─ --auto-remediate triggered → _compose_remediation_prompt() → pass 2
    │
    ▼
[build_trace_from_result() + write_trace()]  YAML trace to research/tmp/build-attempts/
    │
    ▼
Artifacts written: result.json · result.report.md · result.patch · result.run-meta.json
                   research/tmp/build-attempts/{id}.yaml
```

## Design Invariants (from PRD MOM)

| ID | Invariant |
|---|---|
| D-01 | Intake gate runs before every CLI invocation. Not optional (bypassed only by `--skip-normalization`). |
| D-02 | Orchestrator (smart) model handles intake. Execution CLI handles execution. Separate. |
| D-03 | `intent_raw` is immutable. Always preserved in trace exactly as received. |
| D-04 | Execution CLI always receives `intent_normalized` + hygiene stanza. Never raw input. |
| D-05 | Hygiene stanza is generic, project-agnostic, portability-linted. Never project-specific. |
| D-06 | Attack loop default: 2 total passes. `--iterations N` overrides. No unbounded loops. |
| D-07 | Full stdout/stderr to `research/tmp`. Only SHA-256 digests in trace. |
| D-08 | Confirmation loop (`--confirm`) is opt-in. Default is silent passthrough. |

## Security Surface

- Subprocess calls use list form (no `shell=True`) — raw prompts cannot escape the `-p` argument
- All runtime artifacts (traces, stdout/stderr, prompt audits) written 0600; dirs 0700
- `ANTHROPIC_API_KEY` never logged, traced, or persisted
- Stanza portability lint prevents instruction injection via stanza mechanism
- `research/`, `.cdh-prompts/`, `.cdh-locks/` in `.gitignore` — prevents accidental commit
- Checkpoint injection sanitised: JSON-only, 64 KiB cap, ownership checks, "UNTRUSTED" wrapper

## File Structure

```
src/code_delegation_harness/
├── harness.py          # Orchestration core, CLI entry point
├── intake.py           # Intake gate (detection, normalisation, orchestrator backends)
├── trace.py            # Build attempt trace schema + writer + prune
├── smoke.py            # Manifest diffing + T1/T2/T3 smoke tests
├── stanzas/
│   ├── __init__.py     # load_stanza(), assert_stanza_portable(), STANZA_VERSION
│   └── base_v1.0.txt   # Hygiene stanza v1.0
├── prompts/
│   └── normalization_v1.0.txt   # Versioned normalisation system prompt
├── status.py           # StatusManager, crash protection
├── cli.py              # Console script entry point
└── __main__.py         # python -m support
```

## Future Directions (Phase 6+)

- Stanza modules for domain-specific engineering standards (infrastructure, web, data pipeline)
- Smoke T4 — behavioural smoke tests (out of scope for harness; human gate or external suite)
- Additional execution CLI adapters (deeper Claude Code, Codex integration)
- Normalization prompt versioning UI (A/B compare, quality metrics across prompt versions)
