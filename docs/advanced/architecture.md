# Architecture Overview

This document describes how the Code Delegation Harness is structured at a high level.

## Core Components

### 1. CLI Entry Point (`src/code_delegation_harness/cli.py` and `__main__.py`)

The main command (`gcdh`) is defined here. It handles argument parsing, validation, and orchestrates the delegation lifecycle.

### 2. Harness Core (`src/code_delegation_harness/harness.py`)

This is the heart of the system. Key responsibilities:

- Building the strong system prompt (`build_grok_prompt`)
- Calling the inner model in headless mode (`call_model_headless`)
- Waiting for background completion (`_wait_for_background_completion`)
- Normalizing raw results into structured artifacts (`normalize_result`)
- Generating human-readable reports (`render_human_report`)
- Producing ready-to-apply patches

### 3. Status Management (`src/code_delegation_harness/status.py`)

Centralized, resilient handling of `.cdh-run-*.status` files:

- `StatusManager` class
- Atomic secure writes (0600)
- Self-healing recovery (`ensure_recoverable`)
- Lightweight polling with throttling
- Full prompt storage for faithful resume

This layer exists so that long-running and background delegations remain observable and recoverable even across process restarts or crashes.

**Resilience primitives (added for crash / long-running survival):**
- `heartbeat()`, `looks_dead()`, `mark_crashed()` on StatusManager + `register_crash_protection()` (atexit + SIGTERM/INT best-effort).
- `--reap-dead`: bulk mark silent runs crashed using looks_dead.
- `--detach`: Unix daemon launch (nohup+setsid) for survival of terminal/parent death.
- `--resume` on "crashed" state: auto-injects `load_checkpoint_context()` (PROGRESS.json etc) + recovery instructions into prompt; sets `resumed_from_crash` for reports.
- Baked prompt mandates frequent PROGRESS.json checkpoints + upfront planning/self-review for complex tasks (survive harness or inner death).
- `RetryPolicy` + self-heal `ensure_recoverable()` + throttled writes for robustness.

Limitations acknowledged in code: SIGKILL unrecoverable by handlers; no HB during inner model call (long tasks >5min may false-positive as dead to observers); primarily Unix for signals/detach. Use --reap + checkpoints for full coverage.

### 4. Output Artifacts

When a delegation completes, the harness produces:

- `result.json` – Structured machine-readable output
- `result.report.md` – Human-scannable review document with Quick Review Checklist
- `result.patch` (when changes were made) – Unified diff ready to apply
- `result.run-meta.json` – Reproducibility metadata

See [output-artifacts.md](../usage/output-artifacts.md) for the detailed schema.

## Design Principles

- **Model-agnostic where possible**: The `--model` flag and thin adapter layer are intended to make swapping backends relatively straightforward.
- **Strong working directory discipline**: The harness is obsessive about making sure the inner model only operates inside the exact directory the user specified.
- **Reviewability first**: Every run should produce artifacts that a human (or another agent) can quickly evaluate without re-running the entire task.
- **Lightweight and recoverable**: Background and long-running support is a first-class concern. The StatusManager + recovery logic exists specifically for this.
- New (0.3.x+): Auto tmux escape from hostile short-timeout launchers (TUI, CI wrappers) when --long-running or --tmux is used. Auto-reap of dead prior runs on every serious launch. Strict safe isolated workspace + promotion-only mutation discipline enforced in prompts to guarantee no partial broken state is ever left in live dogfood targets.

## Data Flow (Simplified)

1. User invokes `gcdh` with task + target directory.
2. Harness builds a high-signal prompt that includes strict path rules and a required structured summary format.
3. The inner model (via `grok` CLI or future adapters) is invoked.
4. If it times out and `--wait-for-completion` is set, the harness enters a resilient polling loop using the status file. (Post-2026-05 hardening: every probe dynamically reloads + injects the *latest* agent `PROGRESS.json` + anti-stale instructions so long jobs make real incremental progress across interruptions. `--long-running` bumps all budgets and activates the full ruthless "job-to-the-end" prompt language.)
5. On completion, raw output is parsed for the `=== DELEGATION SUMMARY ===` block. If the exact markers are missing (common on long runs), best-effort synthesis is performed using the agent's `PROGRESS.json` checkpoints. The result is marked with `summary_synthesized_from_checkpoint`.
6. Results are normalized, diffs are computed, a patch is generated if needed, and all artifacts are written.

## Recovery & Observability

The `.cdh-run-<id>.status` files are the source of truth for long-running work. They contain:

- Full original prompt (for faithful resume)
- Task, context, constraints
- Current state (launched / waiting / running / completed / max_wait_exceeded)
- Timestamps and error history

This allows `--status`, `--resume`, and `--prune` to work reliably.

## Future Directions

- Additional model backends
- Richer observability (metrics, better logging)
- First-class support for multi-turn agentic loops inside the harness itself

See the [roadmap](../roadmap.md) (when written) for current priorities.
