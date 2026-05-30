# Security Policy

## Reporting a Vulnerability

If you discover a security issue in this project, please report it responsibly.

**Preferred method:**
- Open a private security advisory on GitHub: https://github.com/joshuafielden43/code-delegation-harness/security/advisories/new

**Alternative:**
- Email the maintainer directly (see repository contact if available).

We take security seriously, even for a small tool. Responsible disclosure is appreciated and we will work with you on a fix and coordinated disclosure.

## Scope

This policy covers the core `code-delegation-harness` CLI and library code.

It does **not** cover:
- Security issues in the LLMs or coding models you choose to use with the harness.
- Issues in third-party tools, packages, or code that the harness delegates work to.
- Misuse of the harness to generate malicious code.

## Supported Versions

We generally only support the latest release on the `main` branch for security fixes.

## Thanks

We appreciate security researchers and users who help keep this tool safe.

## Threat Model for Background / Long-Running Features (2026-05-30)

The resilience features (heartbeats, crash protection, `--reap-dead`, `--detach`, checkpoint-based auto-recovery on `--resume`, and rich status files) intentionally increase observability and recoverability. They do so by creating persistent artifacts and recovery paths that read from the user-supplied `--target-dir`.

**Assumptions / Safe Usage:**
- `--target-dir` (and any files the inner agent writes, including PROGRESS.json / checkpoints) is **trusted and private** to the user running the harness.
- Status files (`.cdh-run-*.status`) contain the full original task/prompt/context. Protect the directory.
- Do **not** use `--detach`, `--reap-dead`, or `--resume` (especially on crashed runs) on shared workstations, CI workspaces, NFS mounts, or any location where an untrusted party can write files into the target directory.

**Known Residual Risks (after P0/P1 mitigations):**
- Prompt injection via planted checkpoints on `--resume` of crashed runs (mitigated with size cap, ownership check on load, and explicit "UNTRUSTED" wrapper + warnings in injected text).
- Status file tampering / information disclosure if directory permissions are weak (mitigated with owner+mode verification on security-sensitive loads and 0600 creation).
- Crash marking from signals is best-effort (sentinel files + best-effort full mark; SIGKILL/OOM/power loss cannot be caught).
- `--detach` is Unix-only and inherits the full environment/privileges of the launching user.
- The operational monitor script (`scripts/monitor_cdh_status.py`) performs **read-only** scans of status files (same trust model and target-dir assumptions as `gcdh --status`). It never writes to or executes inside target directories.

Users operating in multi-tenant or low-trust environments should treat long-running delegation as a privileged operation and isolate target directories accordingly.

See also `MEETING_OF_MODELS_TRANSCRIPT.md` (repo root) for the complete record of the QA + Security + DevOps review that drove the P0/P1 mitigations, plus the exact residual risk list that remains after hardening. The operational runbook (`docs/operations/runbook-resilience.md`) contains the corresponding deployment guidance.

See also the full `SECURITY_REVIEW.md` (generated during the 2026-05-30 model review + follow-up hardening pass) for detailed analysis, current residual risks after owner-check + sentinel + legacy-write fixes, and the exact mitigations applied.
