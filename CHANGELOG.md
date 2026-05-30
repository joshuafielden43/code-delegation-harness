# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
