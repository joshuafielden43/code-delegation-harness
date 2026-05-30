# Contributing (Development Guide)

This document contains development-specific contribution guidance. For the general contribution process, see the root [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Development Principles

- We treat the public CLI surface and output artifacts as a contract.
- Documentation is part of the deliverable.
- We prefer boring, reliable code.

## Running the Test Suite

See [development-setup.md](development-setup.md) for environment setup.

```bash
python -m pytest tests/ -v
```

## Using the Harness on the Harness

We strongly encourage using the tool itself when making changes:

```bash
gcdh --task "Refactor X to be clearer" --target-dir . --output-file changes.json
```

Then review the generated `.report.md` and `.patch`.

## Pull Request Guidelines

- Keep PRs focused.
- Update or add documentation when behavior changes.
- Make sure CI is green.
- The owner can fast-merge using admin rights on green PRs when appropriate.

## Release Process

See [release-process.md](release-process.md) for how releases are currently handled.
