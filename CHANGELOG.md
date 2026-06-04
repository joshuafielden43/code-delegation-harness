# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — Unreleased

### Summary
0.4.0 transforms the harness from a clean CLI wrapper into a closed-loop quality system.
The core addition is an **intake gate** that runs before every CLI invocation: it detects
whether a prompt is human or AI-structured, normalises it via an orchestrator model,
extracts a typed artifact manifest, and pre-generates an adversarial attack frame — all in
a single call before the execution CLI is touched. A **hygiene stanza** (v1.0, version-pinned,
portability-linted) is injected into every normalised prompt. A **build attempt trace** (YAML)
is written for every run. Post-run **manifest diffing** and **smoke testing** (T1/T2/T3)
provide ground-truth verification. The attack loop now uses real filesystem evidence, not model
self-reporting.

### New: Intake Gate (Phase 2)
- `intake.py` — orchestrator gate with four operations per invocation: prompt detection,
  normalisation, manifest extraction, attack frame pre-generation.
- `detect_prompt_type()` — schema validator (~5 lines) distinguishing human vs AI-structured
  prompts. AI-structured prompts pass through unchanged (`was_normalized=false`).
- `AnthropicOrchestratorBackend` — uses Anthropic SDK with native `tool_use` for structured
  output. No `instructor` dependency. Install with `pip install "code-delegation-harness[intake]"`.
- `CLIOrchestratorBackend` — fallback using the execution CLI subprocess; zero extra deps.
- `get_orchestrator(provider="auto")` — auto-detects `ANTHROPIC_API_KEY`; falls back to CLI.
- Graceful degradation: any intake failure passes raw prompt through with warning. Never aborts.
- Intake call wrapped in `RetryPolicy(max=3, base=2s)` — transient network errors do not
  immediately degrade the run.
- New flags: `--orchestrator-model`, `--orchestrator-provider`, `--orchestrator-timeout`,
  `--skip-normalization` (bypasses intake AND stanza injection entirely).

### New: Hygiene Stanza (Phase 3)
- `stanzas/base_v1.0.txt` — generic, portable, project-agnostic v1.0 stanza covering five
  universal engineering standards. Appended to every normalised prompt.
- `assert_stanza_portable()` — portability lint that fails if the stanza contains any
  project-specific file names, paths, or tool names. Enforced at load time.
- Stanza module plugin slot (`stanza_modules: [base]`) ready for Phase 6 domain extensions.
- New flags: `--no-hygiene` (skip injection), `--stanza-modules` (select modules).

### New: Build Attempt Trace (Phase 1 / trace.py)
- Every run produces a YAML trace at `{research-dir}/build-attempts/{id}.yaml` (0600).
- Schema covers: intent (raw + normalised) · intake · confirmation · manifest · runs with
  SHA-256 output digests · attack critique · verdict with smoke tier.
- `--research-dir` flag (default: `{target-dir}/research/tmp`) for all runtime artifacts.
- Full stdout/stderr written to `research/tmp` (0600); only SHA-256 digests in trace (D-07).
- Trace path included in result JSON (`build_attempt_trace`) and in `.report.md`.
- `--prune-research [N]` — purge traces and stdout/stderr artifacts older than N days
  (default 7). Mirrors `--prune` for status files.

### New: Confirmation Loop (Phase 4)
- `--confirm` — opt-in flag (off by default; never interrupts automated pipelines).
- Shows normalised intent + expected artifact list before CLI runs.
- Accepts one correction input; re-normalises via orchestrator; re-shows updated manifest.
- Hard cap: 2 rounds, proceeds regardless. Corrections captured in trace for tuning data.

### New: Manifest Diffing + Smoke Testing (Phase 5 / smoke.py)
- `diff_manifest()` — post-run filesystem scan vs `manifest.expected`. Produces `found` and
  `missing` lists from ground truth, not model self-reporting.
- Missing artifacts injected into the attack prompt as explicit `spec_coverage` weakness items.
  The attack loop now targets what is actually absent on disk.
- `run_smoke_tests()` — T1 (artifact exists), T2 (Python import exits 0), T3 (AST public-name
  conformance). Result in `verdict.smoke_tier` and `smoke` dict in result JSON.
- `manifest_found` / `manifest_missing` in result JSON.

### New: Normalization Prompt Versioning (OQ-02)
- `prompts/normalization_v1.0.txt` — the intake system prompt is now a versioned file.
  Edit it to improve normalisation quality without touching Python source.
- `NORMALIZATION_PROMPT_VERSION = "normalization-v1.0"` constant.
- `normalized_via.prompt_version` in trace reflects which version ran.

### New: `--iterations` Flag (Phase 1 / D-06)
- `--iterations N` — total pass cap including original run. Aliases/replaces
  `--remediation-max-passes`. Default: 2 (1 original + 1 attack pass). `--iterations 1`
  means no attack passes. Warning emitted if both flags are supplied.

### Model-Agnostic Rename
- `build_grok_prompt` → `build_execution_prompt` (old name kept as backward-compat alias).
- Internal "Grok"-specific strings neutralised in reports and dry-run output.
- Dry-run preview now shows full Phase 2-4 configuration (orchestrator, stanzas, confirmation,
  iterations).

### Security / Operational
- `research/`, `.cdh-prompts/`, `.cdh-locks/` added to `.gitignore` (prevents accidental
  commit of traces with full task text and API responses).
- `ensure_research_dir()` calls `chmod(0o700)` on every invocation, fixing pre-existing
  loose-permission directories.
- `intake_status` field in result JSON: `success | degraded | error | skipped | unavailable`.
  `ImportError` caught separately with install hint.
- Research write failures logged to stderr (no longer silently dropped).
- `--confirm` + unavailable intake: explicit warning rather than silent skip.

### Dependency Change
- `[intake]` extra simplified: `anthropic>=0.40.0` only. `instructor` and `pydantic` removed
  (native `tool_use` replaces instructor-based structured output).

### Tests
- 61 → 153 tests (all passing). New test files: `test_trace.py`, `test_stanzas.py`,
  `test_intake.py`, `test_confirmation.py`, `test_research_prune.py`, `test_smoke.py`.

## Unreleased (pre-0.4.0)

### Long-Running Visibility & Launcher Escape
- Added support and strong recommendations for `--long-running` (and `--keep-driving` alias) as the primary mode for serious, ambitious dogfood and implementation work. This mode:
  - Auto-bumps limits (`--timeout`, `--max-turns`, `--max-wait`, etc.) when set.
  - Wires extra emphasis into the prompt for "job to the end" behavior.
  - Enables automatic hostile launcher escape (tmux) when launched from short-timeout environments (Grok Build TUI, CI wrappers, etc.).
  - Triggers aggressive auto-reap of prior dead runs on launch.
- Added `scripts/gcdh-tmux` as a convenient one-command launcher that handles the tmux escape pattern safely.
- Added **SAFE LIVE-TARGET MUTATION DISCIPLINE** (enforced in both the core prompt and key dogfood prompts): all development work must happen in an isolated copy inside the harness `--target-dir`. The only allowed mutation to a live target is a single final atomic promotion of a complete, tested, reviewable result. This directly addresses the recurring failure mode where a killed run left partial/broken edits in the real target (e.g. Proxmox skill) that then required manual outer repair before the next run could even validate.
- Strengthened `--reap-dead` and status monitoring paths with `check_pid` support to reduce false positives on long-running jobs.
- Improved `gcdh-tmux` command reconstruction to use safe quoting (via `shlex`) instead of raw `$*`, preventing injection risks and mangled tasks with special characters or quotes.
- Various hygiene and correctness fixes in monitoring and status paths (e.g. `--pid-check` behavior in `monitor_cdh_status.py` now actually suppresses false positives when the PID is alive).

### Dogfood Tooling & Ongoing Normalization Work
- Added `tag-nuc-casing-micro.md` and companion `tag-nuc-casing-apply.md` prompts. These enable tightly scoped, high-discipline micro-passes to resolve specific open threads (such as the nuc casing conflict surfaced during v5) while maintaining all strict validation gates, rich PROGRESS checkpoints for reviewer notes, and the candidate → temp-snapshot → promote discipline.
- Continued active dogfooding of small, controlled tag normalization slices on 0.3.1 (v5 controlled widening followed by nuc micro). This validates the harness for real many-small-edits grooming workloads and exercises the improved synthesis + reporting paths.

### Repository & Release Hygiene
- Significant worktree cleanup and improved tracking of active dogfood prompts and the single source of truth transcript.
- Ongoing maintenance of the `MEETING_OF_MODELS_TRANSCRIPT.md` with current dogfood status to keep the authoritative record up to date.

### Launcher Escape & Broken-Artifact Prevention (direct response to outer 300s SIG15 + manual repair incident)
- Added **SAFE LIVE-TARGET MUTATION DISCIPLINE** (ruthless new section in the core `build_grok_prompt` + mirrored into the Proxmox appliance provisioning dogfood prompt). Live locations (real skill trees, infra control planes) are now *structurally* read-only for development. The harness contract is explicit: all work happens in an isolated copy inside the harness target_dir; the *only* allowed mutation to the live target is a single final atomic promotion of a complete, tested, reviewable patch set. A killed run must leave the live dogfood target byte-identical to launch state. This directly prevents the recurring failure where a harness death left partial guest-exec classification, wrong LXC exec paths (pct vs pvesh), and broken state in `~/.hermes/skills/proxmox-control/` that required an "outer Honey repair pass" before the next run could even smoke-test.
- Automatic **HOSTILE LAUNCHER ESCAPE** recipe printed for every `--long-running` serious task when launched from inside short-timeout wrappers (the Grok Build TUI, grok CLI contexts, CI with hard 300s kills, etc.). Detects the environment and emits a ready-to-paste `tmux new-session -d ...` one-liner that survives the outer SIG15 wrapper + the exact safe-mutation reminder. This is the concrete product answer to running substantial delegated work through constrained harness environments.
- These two changes together close the loop on the "harness dies → partial live edits → human has to fix the target by hand" pattern observed in the most recent Proxmox appliance provisioning dogfood run. Future long-running runs on real targets are now structurally prevented from leaving the kind of mess that forces outer intervention.

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
