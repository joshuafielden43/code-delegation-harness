# Contributing to Code Delegation Harness

Thank you for your interest in contributing. This project aims to be a reliable, professional tool for delegating coding work to LLMs while keeping the primary agent clean.

We use the harness itself for development work where practical.

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
