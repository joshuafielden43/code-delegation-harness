# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
