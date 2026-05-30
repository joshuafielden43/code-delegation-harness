# Contributing

Thank you for your interest in contributing to the Grok Coding Delegate!

## Development Setup

```bash
git clone https://github.com/<org>/grok-coding-delegate.git
cd grok-coding-delegate
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running Tests

```bash
python -m unittest discover -s tests
```

## Code Style

- Keep the public CLI surface stable.
- New features should have corresponding tests.
- Documentation (especially the structured JSON output and CLI behavior) is part of the public contract.

## Submitting Changes

1. Fork the repository.
2. Create a feature branch.
3. Make your changes with tests.
4. Open a Pull Request with a clear description of the change and why it is needed.

We use the harness itself for development where possible.
