# Development Setup

This guide explains how to get the Code Delegation Harness running locally for development and contribution.

## Prerequisites

- Python 3.9+
- Git
- A virtual environment tool (venv recommended)

## Clone and Install

```bash
git clone https://github.com/joshuafielden43/code-delegation-harness.git
cd code-delegation-harness

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install the package in editable mode with development dependencies
pip install -e .
pip install pytest
```

## Running Tests

```bash
# Recommended
python -m pytest tests/ -v

# Fallback (if pytest has issues)
python -m unittest discover -s tests -v
```

## Running the CLI Locally

After installing in editable mode, the `gcdh` command should be available:

```bash
gcdh --help
```

If the command is not found, ensure your virtual environment is activated and that you installed with `pip install -e .`.

## Using the Harness on Itself

We dogfood the harness heavily. You can use it to work on the harness codebase:

```bash
gcdh --task "Improve error messages in the status manager" \
     --target-dir . \
     --output-file my-changes.json
```

## Code Style

- Keep public CLI behavior and output artifacts stable.
- New functionality should come with tests.
- Documentation is part of the product contract.
- Prefer clear, maintainable code over cleverness.

## Next Steps

- See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the contribution process.
- See [Testing](testing.md) once that document is written.
- See [Architecture](../advanced/architecture.md) for how the harness works internally.
