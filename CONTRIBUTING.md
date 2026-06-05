# Contributing to Code Delegation Harness

Thank you for your interest in contributing. This project aims to be a reliable, professional tool for delegating coding work to LLMs while keeping the primary agent clean.

We use the harness itself for development work where practical.

## How This Project Actually Works

This project is built and reviewed by a team of human and AI collaborators. Understanding the division of labour prevents confusion and wasted effort.

**Joshua Fielden (Nonesuch Applied Infrastructure)** — product owner and architect. Defines requirements, makes binding decisions, owns the Hermes production environment.

**Claude (Anthropic)** — implementation. Writes code, tests, and documentation. Works in `~/Projects/code-delegation-harness`. Commits to GitHub. Does not touch the production Hermes skill install.

**Honey Nous** — review and hardening. Conducts multi-perspective MoM reviews (QA · DevOps · InfoSec) against each release candidate. Does not have access to `~/Projects/` or any `~/.[harness]` paths — reviews from GitHub only.

**Grok Code / Codex** — prior implementation contributions; see CONTRIBUTORS.md.

### The Release Gate

No code is promoted to the production Hermes skill (`~/.hermes/skills/software-development/code-delegation-harness`) without passing through this gate:

1. **Build** — Claude implements on the feature branch, all tests pass, CI is green.
2. **MoM review** — Honey conducts a Meeting of Models review: QA, DevOps, and InfoSec perspectives independently, then synthesised. Findings are raised as issues with severity ratings.
3. **Remediation** — All critical and high findings are addressed before merge. Medium findings are addressed or explicitly deferred with rationale.
4. **Merge to main** — Squash merge via PR after CI passes.
5. **Promote to production** — Joshua manually promotes `main` to the Hermes skill when satisfied. This step is never automated.

This pattern has caught 4-5 real bugs per release cycle. The value is the cold read — Honey reviews without implementation context, which surfaces assumptions the implementer doesn't see.

### Access boundaries

| Collaborator | `~/Projects/` | `~/.[harness]` | GitHub |
|---|---|---|---|
| Claude | ✅ read/write | ✅ read/write | ✅ push |
| Honey | ❌ | ❌ | ✅ read only |
| Grok | varies | varies | ✅ |

These boundaries are intentional and must not be bypassed.

## Development Setup

```bash
git clone https://github.com/joshuafielden43/code-delegation-harness.git
cd code-delegation-harness

# Recommended: use a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .

# Install test dependencies
pip install pytest
```

## Running Tests

```bash
# Preferred
python -m pytest tests/ -v

# Fallback
python -m unittest discover -s tests -v
```

## Code Style & Principles

- The public CLI surface and output artifacts (`.json`, `.report.md`, `.patch`) are the contract. Changes here require strong justification and documentation updates.
- New features should include tests.
- Error messages and UX should be actionable.
- Keep the core lightweight and recoverable (see StatusManager and recovery logic).
- We prefer clear, boring code over clever code.

## Documentation

Documentation is part of the product. Significant changes should include updates to the relevant docs in `docs/`.

See [docs/DOCUMENTATION-STRUCTURE.md](docs/DOCUMENTATION-STRUCTURE.md) for the target state of documentation.

## Submitting Changes

1. Fork the repository.
2. Create a feature branch from `main`.
3. Make your changes with tests and documentation updates.
4. Open a Pull Request against `main`.
5. Ensure CI passes.
6. Be responsive to review feedback.

We generally prefer squash merges for feature work to keep history clean.

## Reporting Issues

- Bug reports: Use the bug report template.
- Security issues: See [SECURITY.md](SECURITY.md) — do **not** open public issues.
- Feature requests / ideas: Open a discussion or issue with clear use case.

## Questions

For usage questions, check the documentation first (especially `docs/usage/for-agents-and-sidecars.md` and the CLI reference).

For development questions, open an issue with the `question` label.
