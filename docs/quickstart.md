# Quickstart

This guide will get you from zero to your first delegation in under two minutes.

## 1. Install

```bash
pip install code-delegation-harness
```

See the [Installation guide](installation.md) for other options (development installs, etc.).

## 2. Run Your First Delegation

```bash
gcdh \
  --task "Add a Google-style docstring and type hints to the main function in main.py" \
  --target-dir /path/to/your/project \
  --output-file my-first-run.json
```

## 3. Review the Output

After it completes, you will have:

- `my-first-run.json` — Structured machine-readable results
- `my-first-run.report.md` — Human-optimized review document
- `my-first-run.patch` — Ready-to-apply unified diff (if changes were made)
- `my-first-run.run-meta.json` — Reproducibility metadata

Open `my-first-run.report.md` first. It is designed to be the primary thing you review.

## Next Steps

- Read the [Usage Notes](usage-notes.md) for best practices
- See [Examples](examples/) for more realistic scenarios
- Read [For Agents and Sidecars](usage/for-agents-and-sidecars.md) if you are building automation on top of this
