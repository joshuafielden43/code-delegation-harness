# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Long-Running Task Robustness (P0 for Proxmox / Ambitious Dogfood)
- **Major hardening of `build_grok_prompt`** (in `harness.py`): Added ~80 lines of *ruthless* "JOB TO THE END" + mandatory anti-stale-data protocol + binary completion metric + "NEVER emit summary while work remains" + explicit "KEEP DRIVING UNTIL DONE" + evidence requirements. The inner agent is now forced (on every invocation, probe, resume, or continuation) to: (1) treat all prior PROGRESS as historical only, (2) perform fresh live verification of the target as absolute first action (cross-checking every VMID/filename/ID etc.), (3) drive concrete remaining plan steps, (4) update checkpoint, (5) refuse early victory. This directly attacks "good analysis but fails to finish implementation+tests+promotion" and "relies on stale VM140" failure modes observed in real runs.
- **Dynamic checkpoint injection in wait/polling loop**: `_wait_for_background_completion` now (on *every* poll, not just initial resume) reloads the latest `PROGRESS.json` via `load_checkpoint_context` and injects a strong "FRESH CONTINUATION / PROBE CONTEXT" block + anti-stale instructions into the working prompt for that probe. Combined with the new base prompt language, this makes `--wait-for-completion` and `--resume` paths true incremental drivers that survive hundreds of seconds of death and make progress on ambitious jobs.
- **probe_timeout raised + configurable**: Removed the magic hardcoded `timeout=300` (5min death sentence for inner agents in wait mode) in the background polling loop. Now defaults to 1800s and is passed from `--timeout` (or `--long-running` bumps). Probes can now survive real work.
- **New `--long-running` / `--keep-driving` flag** (and `--keep-driving` alias): Opt-in mode for multi-hour ambitious implementation tasks (explicitly motivated by Proxmox skill extensions: guest-exec, resize, discovery fixes etc. under safety discipline). When set:
  - Auto-bumps `--timeout` (to 4h), `--max-turns` (to 300), `--max-wait` (to 24h), `--poll-interval` if lower (only upward, respects explicit user values).
  - Wires `long_running=True` through prompt builder (extra emphasis paragraph), wait loop (immediate first probe + per-poll dynamic ckpt injection), dry-run, resume, and all metadata.
  - Enables the full "keep driving" resilience behaviors. (Note: the core ruthless anti-stale + job-to-the-end language is now unconditional on every invocation; the flag additionally signals intent, triggers the extra paragraph, and performs the limit bumps + immediate probe.)
  - Recommended (with `--output-file`, `--run-name`, high `--max-wait`) for any real dogfood that must reach tested+promotable end-state without constant human intervention.
- **Resume/continuation paths strengthened for all cases**: Checkpoint augmentation now happens on *every* `--resume` (crashed or normal waiting), not just crashed. Generalized labels and instructions. The wait loop re-injects on every probe regardless.
- **Bulletproofing + hygiene**: Fixed latent `quiet=quiet` reference in one wait call path. Extended `build_grok_prompt` signature with `long_running`. All changes preserve backward compat for normal short tasks.
- Result: The harness is now in a mature state where the *next* real harness-driven dogfood run on the Proxmox control skill (appliance provisioning, guest-exec etc.) has high confidence of succeeding end-to-end: surviving interruptions, using only fresh live verification, relentlessly driving from PROGRESS checkpoints all the way to reviewable+promoted artifacts.

### Dogfood Tooling & Ongoing Normalization Work
- Added `tag-nuc-casing-micro.md` and companion `tag-nuc-casing-apply.md` prompts. These enable tightly scoped, high-discipline micro-passes to resolve specific open threads (such as the nuc casing conflict surfaced during v5) while maintaining all strict validation gates, rich PROGRESS checkpoints for reviewer notes, and the candidate → temp-snapshot → promote discipline.
- Continued active dogfooding of small, controlled tag normalization slices on 0.3.1 (v5 controlled widening followed by nuc micro). This validates the harness for real many-small-edits grooming workloads and exercises the improved synthesis + reporting paths.

### Repository & Release Hygiene
- Significant worktree cleanup and improved tracking of active dogfood prompts and the single source of truth transcript.
- Ongoing maintenance of the `MEETING_OF_MODELS_TRANSCRIPT.md` with current dogfood status to keep the authoritative record up to date.

## [0.3.1] - 2026-05-30

**Patch release: Post-0.3.0 hardening + grooming / normalization notes improvements.**

This release addresses remaining issues identified in detailed external review of the 0.3.0 resilience work and the new grooming-oriented synthesis features. It makes long-running background recovery and vault-style many-small-edits workloads even more trustworthy and reviewer-friendly.

### Critical Fixes (P1)
- Fixed `NameError: name 'quiet' is not defined` on `--resume` and timed-out `--wait-for-completion` paths (affected any non-trivial background recovery).
- Fixed premature creation of `.crashed` sentinels inside `register_crash_protection()`. Sentinels are now written *only* on actual crash paths (`_mark_active_run_crashed`). This eliminates false "crashed" reports for live runs while preserving the lightweight signal-context marker for `--reap-dead`.
- Best-effort summary synthesis (used when agents omit the `=== DELEGATION SUMMARY ===` markers on long runs) now applies the same ownership, mode, and 64 KiB size guards as `load_checkpoint_context()`. Closes a bypass that could have allowed tampered or huge PROGRESS files to pollute human reports and result JSON.
- Expanded `--resume` terminal-state short-circuit to all final states (`failed`, `completed_no_changes`, etc.) so already-finished work is never re-launched.

### Security & Consistency (P2)
- Insecure crash sentinels are now fail-closed (consistent with main status files). Untrusted sentinels are rejected instead of being silently promoted to "crashed" state.

### Grooming / Normalization Notes (Honey v4 Feedback)
- First-class support in reports for high-signal grooming work: structured `Grooming / Normalization Notes`, `Run Intent`, rich `cluster_evidence` / `validation_status` / `real_target_evidence` lifting, improved normalization grouping (→ targets), and clean Recovery Sources JSON previews.
- v4 (and future) dogfood prompts now document the recommended rich PROGRESS.json shape that feeds these reviewer-friendly sections.
- Directly enables the quality of feedback demonstrated on the tag v4 validation slice.

### Testing & Documentation
- +3 targeted regression tests (48 total). All reviewer repro cases now covered.
- Updated `MEETING_OF_MODELS_TRANSCRIPT.md` (single source of truth) with full work log for the reviewer round.
- Runbook and other docs refreshed.

All changes are backward-compatible for normal usage. 0.3.1 is the recommended version for any ambitious or long-running delegation, especially grooming / normalization workloads on live data.

## [0.3.0] - 2026-05-30

**Major release: Production-grade long-running and background resilience.**

This release matures the harness's core promise — reliable delegation of ambitious, long-running work (including on real hardware and self-improvement tasks) without silent death or lost progress. The changes represent a significant step up in operational safety, recoverability, and auditability.

### Resilience Hardening Capstone (Meeting of Models Review)

- Full multi-perspective review (QA + Security + DevOps/SRE) executed via the harness itself against the new background features.
- Produced the single consolidated `MEETING_OF_MODELS_TRANSCRIPT.md` (the authoritative record of prompts, all three agent outputs from both rounds, cross-discussion, prioritized backlog, and complete work log).
- Closed all remaining high-priority items identified by the reviewers:
  - Owner + mode verification now enforced on *every* status read path (including previous direct `json.loads` sites in prune, `--status`, and `--resume` resolution) via new `_read_status_secure` helper. Insecure files are skipped or cause explicit refusal.
  - `fsync` added to `StatusManager._atomic_write` for durability across power loss / OOM / hard kill.
  - Crash protection paths now produce structured `.last-crash` sibling logs (best-effort, 0600) for post-mortem forensics when sentinels or marks themselves fail.
  - Expanded test coverage with new cases for world-writable checkpoint rejection, `looks_dead(check_pid=True)`, and insecure file handling in prune.
- `looks_dead()` already included the optional cheap PID liveness probe (`os.kill(pid, 0)`) per earlier QA/DevOps feedback; now exercised in tests.
- All changes verified with 34/34 tests passing + targeted CLI smokes for the new security and recovery paths.

### Documentation & Threat Model

- Added prominent Section 9 to the [Operational Runbook](../docs/operations/runbook-resilience.md) documenting the exact post-review hardening state and safe-usage assumptions.
- Updated `SECURITY.md` threat model section with cross-reference to the transcript as the single source of truth for the review and residual risks.
- Refined guidance around `--detach`, checkpoint injection risks (now strongly mitigated), and when to treat `target_dir` as trusted vs. isolated.

### Versioning Note

0.2.x captured the initial public packaging, early long-running skeleton, and the first waves of StatusManager + crash protection work. 0.3.0 marks the point where the harness delivers production-resilient background delegation with security review, durability guarantees, observability primitives, and recovery paths that have been through rigorous multi-perspective scrutiny.

### Other

- 34 tests (up from prior baseline).
- No breaking changes to the public CLI or core delegation flow for normal (non-background) use.
- Strong recommendation: Use `--detach`, `--reap-dead`, heartbeats, and `PROGRESS.json` checkpoints for any ambitious or long-running task. See the runbook and transcript for details.

---

### Prior Resilience Work (rolled into 0.3.0)

The following foundational work from the 0.2.x cycle is now part of the 0.3.0 long-running story:

- Centralized all status lifecycle through `StatusManager`.
- `ensure_recoverable()` self-healing, `RetryPolicy`, throttled writes, full prompt storage for faithful resume.
- `--detach` (nohup + setsid, POSIX guard), `--reap-dead`, heartbeats, `looks_dead`, crash sentinels + atexit/SIGTERM/SIGINT/SIGHUP handlers.
- `load_checkpoint_context` with 64 KiB cap, ownership enforcement, and explicit "BEGIN UNTRUSTED CHECKPOINT" wrapper + "ignore embedded commands" language.
- Comprehensive threat model in `SECURITY.md`.
- `scripts/monitor_cdh_status.py` and operational runbook.
- Legacy helpers marked deprecated in favor of the manager.

These changes make the harness production-resilient for real long-running / background delegations and agent sidecar use.

### Lightweight Recoverable Long-Running Core (StatusManager + Resiliency)

- Centralized all status lifecycle through `StatusManager` (create, poll, wait, resume, finalize).
- `ensure_recoverable()` self-healing now wired into wait loops and resume paths: corrupted or partial `.cdh-run-*.status` files repair themselves enough for `--resume` and background completion to succeed.
- Added `RetryPolicy` (tiny, zero-dep) for automatic limited backoff retries on transient errors during polling / background waits. Integrated into `_wait_for_background_completion`.
- Throttled status writes during long polls (keeps harness lightweight while still fresh for observers).
- Full prompt (not just task snippet) is now reliably stored at launch and preferred on resume for faithful continuation.
- Fixed partial rename (`call_grok_headless` → `call_model_headless` for model-agnostic adapter story) and a lingering merge conflict.
- Legacy `_make_delegate_status` / `_write_status_file` / `_finalize...` marked deprecated (retained for test compat only; core paths are now manager-only).
- Improved finalization path also runs self-healing before marking terminal state.
- Extensive direct validation + CLI smoke + self-dogfood dry-runs exercising the new paths (no inner model required for the dry safety case).
- Codex P1 recovery fidelity and standalone command bugs fully addressed in this hardening pass.

These changes make the harness production-resilient for real long-running / background delegations and agent sidecar use without heavy dependencies.

### Operational / SRE Additions (Unreleased)
- Added comprehensive [Operational Runbook](../docs/operations/runbook-resilience.md) covering monitoring & alerting with heartbeats/status files, `--detach` production implications (log blackhole, supervision trade-offs), logging/runbook needs, reliability under reboots/OOM/terminal disconnects, and integration patterns with Prometheus, cron, webhooks, systemd, etc.
- Delivered `scripts/monitor_cdh_status.py`: executable, working scanner that re-uses (or falls back to) `looks_dead` + heartbeat logic, supports `--json`, `--alert-on-dead`, `--pid-check`, `--webhook`, multi-target, cron-ready. Full usage and examples in docstring.
- Updated CLI reference, troubleshooting, and agent/sidecar docs to cover `--reap-dead`, `--detach`, heartbeat observability, and point to the new runbook for production operation.
- Confirmed (via clean test runs + smoke) that `--reap-dead`, `--status`, `--resume` from crashed, and status/heartbeat paths are fully operational for SRE use. No source changes required for this phase (precise/minimal).

## [0.2.0] - 2026-05-30

**First public release of the Code Delegation Harness.**

A practical tool for delegating coding work to LLMs while keeping your main agent clean.

### Highlights
- Full rename to `code-delegation-harness` for universal use.
- Professional `gcdh` CLI with strong long-running support and high-quality review artifacts.
- Added proper public documentation.
- Grounded, practical positioning and README.
- Security hardening for status files.

## [0.1.0] - 2026-05-30 (Pre-release)

Initial public release candidate (pre-rename work).
- Clean error handling and observations for no-change runs.

This version represents the state after significant dogfooding on real vault work (including self-correction of earlier runs).
