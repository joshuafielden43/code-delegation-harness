# Changelog

All notable changes to the Code Delegation Harness (gcdh) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `--dry-run` mode for previewing the exact prompt, configuration, and expected artifacts without launching any delegation or writing files.
- `--prune [N]` (default 7 days) to clean up old completed/failed status files.
- Non-fatal warning when the target directory is not a git repository (affects diff/patch quality).
- `missing_summary_marker` error type in structured output when the inner agent omits the `=== DELEGATION SUMMARY ===` block.
- Always write launch-time status files for full observability (even for short runs when using long-running flags).
- `--version` flag.

### Changed
- Repositioned as production-ready (removed "temporary kludge" framing from user-facing documentation while preserving the dual public tool + sidecar dogfooding narrative).
- Improved `--status` output to clearly separate active vs completed/historical runs.
- Stronger final artifact summary printing when using `--output-file`.
- Status files now persist after background completion for better history and resumption.

### Fixed
- Status file writing during long-running waits (previously could crash on undefined dict).
- Various robustness improvements around background/resume flows and metadata propagation.

## [0.2.0] - 2026-05 (Production Push)

Initial production positioning with mature long-running support, rich human review reports, and reliable artifact generation even after background execution.

Key features at this point:
- Full structured output + high-quality `.report.md` + ready-to-apply `.patch`
- Persistent `.grok-delegate-run-*.status` files with `--status` and smart `--resume`
- `--wait-for-completion` with automatic recovery from inner timeouts
- `--dry-run` preview capability
- Clean handling of no-change / read-only work via observations

*Note: Earlier development was tracked primarily in the Grok-Honey dialogue rather than this changelog.*

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
