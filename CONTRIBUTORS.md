# Contributors

This file recognizes people and collaborators who made meaningful implementation contributions to this repository.

## Maintainer

- **Joshua Fielden** (Nonesuch Industries) — product owner, architect, and primary author. Designed the delegation model, defined all binding decisions, and drove the project from initial concept through PRD v1.0.

## AI Collaborators

- **Claude (Anthropic) — Sonnet 4.6**: PRD v1.0 implementation (intake gate, build attempt trace schema, hygiene stanza, confirmation loop, manifest diffing, smoke testing, normalization prompt versioning, native tool_use structured output), MoM review remediation, model-agnostic rename, full documentation pass.

- **Grok Code (xAI)**: baseline harness implementation, attack loop (`--auto-remediate` / `--remediation-mode targeted-inversion`), long-running mode with tmux escape and dynamic checkpoint injection, StatusManager resilience layer, prompt audit infrastructure.

- **Honey Nous**: multi-perspective quality review (QA · DevOps · InfoSec) — hardening review of the 0.3.0 resilience work, grooming/normalization notes improvements, and the MoM design session that produced PRD v1.0.

- **OpenAI Codex**: automatic pass-2 remediation (counter-prompt mode), remediation metadata and reconciliation, lock/runtime bug fixes, monitor PID-check hardening, and associated test coverage.
