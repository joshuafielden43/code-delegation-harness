# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (with intake gate extras)
pip install -e ".[intake]"

# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_intake.py

# Run a single test
python -m pytest tests/test_intake.py::TestDetectPromptType::test_human_prompt

# Lint portability of the hygiene stanza
python -c "from code_delegation_harness.stanzas import assert_stanza_portable, load_stanza; assert_stanza_portable(load_stanza(['base']))"

# Invoke the harness directly
gcdh --task "..." --target-dir /path/to/project --output-file result.json
```

## Architecture

The harness has one job: take a task, delegate it to a coding CLI, and return structured auditable artifacts. It never runs code itself — it wraps the CLI that does.

### Four-stage pipeline

```
Intake Gate → Confirmation Loop (opt-in) → CLI Execution → Attack Loop (opt-in)
```

Each stage produces a section of the **build attempt trace** (`{research-dir}/build-attempts/{id}.yaml`), which is the canonical record of the run.

### Module responsibilities

| Module | Responsibility |
|---|---|
| `harness.py` | Orchestration core. Owns the full lifecycle. CLI entry point via `gcdh`. |
| `intake.py` | Pre-execution pass: detects prompt type, normalises human prompts, extracts artifact manifest, pre-generates attack frame. Single orchestrator call. |
| `trace.py` | Build attempt trace schema (dataclasses), writer, and pruner. |
| `smoke.py` | Post-execution: `diff_manifest()` filesystem scan + T1/T2/T3 smoke tests. |
| `stanzas/` | Hygiene stanza loader + portability linter. `base_v1.0.txt` is the only live module. |
| `prompts/` | Versioned system prompts. `normalization_v1.0.txt` is the intake normalisation prompt — edit it directly to improve quality without touching Python. |
| `status.py` | `StatusManager`: atomic 0600 status files, heartbeat, crash sentinels, prompt audit trail. |

### Key design invariants

- **D-01**: Intake gate runs before every CLI call. Bypassed only by `--skip-normalization`.
- **D-02**: Orchestrator (smart) model handles intake. Execution CLI handles execution. Never mixed.
- **D-03**: `intent_raw` is immutable. Always preserved verbatim in the trace.
- **D-04**: Execution CLI always receives `intent_normalized` + hygiene stanza. Never raw input.
- **D-05**: Hygiene stanza is generic and project-agnostic. `assert_stanza_portable()` enforces this.
- **D-06**: Attack loop default is 2 total passes. `--iterations N` overrides. No unbounded loops.
- **D-07**: Full stdout/stderr written to `research/tmp`. Only SHA-256 digests appear in the trace.

### Intake gate backends

`get_orchestrator(provider="auto")` selects:
- `AnthropicOrchestratorBackend` — if `ANTHROPIC_API_KEY` is set and `[intake]` extras are installed. Uses native `tool_use`.
- `CLIOrchestratorBackend` — fallback, zero extra deps.

Any intake failure degrades gracefully — raw prompt passes through, `intake_status: degraded` in result. Never aborts.

### Attack loop

When `--auto-remediate` is passed, a second CLI pass runs targeting real gaps. The attack prompt is composed from: (1) LLM-inferred weakness profile from pass 1, (2) actual missing artifacts from `diff_manifest()`, (3) pre-generated attack frame from intake. The prompt is persisted as `<stem>.pass2.prompt.txt`.

### Long-running mode

`--long-running` escapes from TUI/CI wrappers via tmux and enables a resilient polling loop with dynamic `PROGRESS.json` injection. Use this for any ambitious or production delegation. `--wait-for-completion` + `--max-wait` let callers block until done.

### Security surface

- All subprocess calls use list form — no `shell=True`.
- All runtime artifacts written 0600; dirs 0700.
- Checkpoint injection is JSON-only, 64 KiB capped, ownership-checked, wrapped as `UNTRUSTED`.
- `research/`, `.cdh-prompts/`, `.cdh-locks/` are gitignored.

### Normalisation prompt versioning

The normalisation system prompt lives in `src/code_delegation_harness/prompts/normalization_v1.0.txt`. The version string is recorded in every trace under `normalized_via.prompt_version`. To improve normalisation quality, edit the file directly — no Python changes needed.

### Test structure

153 tests across 10 files, one file per module. Tests are the canonical specification for each module's contract. `test_resilience.py` (24 tests) and `test_status_features.py` (15 tests) cover the long-running and audit trail paths specifically.
