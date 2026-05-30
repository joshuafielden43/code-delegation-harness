# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-30

**First public release of the Code Delegation Harness** — now positioned as a universal tool for delegating coding work to LLMs (with excellent first-class support for Grok).

### Highlights
- Full rename and repositioning as `code-delegation-harness` (distribution name, package, documentation, and branding) for broad applicability beyond any single model.
- Internal module renamed from `grok_delegate` to `code_delegation_harness`.
- Status files updated to the clean `.cdh-run-*.status` naming.
- Professional `gcdh` CLI with full `--quiet` / `--verbose`, `--dry-run`, long-running support (`--wait-for-completion`, `--status`, `--resume`, `--prune`), and high-quality artifacts (`.json` + `.report.md` + `.patch`).
- Added proper public documentation (`docs/usage-notes.md`, examples, and case study).
- Significant improvements to the customer-facing README with clearer positioning and Honey's framing contributions around entanglement prevention and backend flexibility.
- Security improvement: status files now written with `0o600` permissions.
- Strong emphasis on clean separation between the primary agent's context and delegated implementation work.

This release represents the completion of the initial public launch preparation, including deep internal cleanup and documentation for a universal audience.

## [0.1.0] - 2026-05-30 (Pre-release)

Initial public release candidate (pre-rename work).

## [0.1.0] - 2026-05-30

Initial public release candidate.

### Highlights
- Production-oriented CLI with `--quiet` / `-q` and `--verbose` / `-v` support.
- Professional front-end experience via `bin/gcdh` (and upcoming `pip install` support).
- Mature long-running support (`--wait-for-completion`, persistent status files, `--status`, `--resume`, `--prune`).
- High-quality review artifacts by default (structured JSON + human `.report.md` + ready-to-apply `.patch`).
- `--dry-run` for safe previewing of complex tasks.
- Clean error handling and observations for no-change runs.

This version represents the state after significant dogfooding on real vault work (including self-correction of earlier runs).
