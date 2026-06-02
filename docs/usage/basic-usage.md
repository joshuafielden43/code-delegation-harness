# Basic Usage

This guide covers the core workflow of using the Code Delegation Harness.

## Quick Start

```bash
# Run a simple delegation
gcdh --task "Add input validation to this function" \
     --target-dir /path/to/your/project \
     --output-file result.json
```

## Core Concepts

- **Task**: The natural language instruction you give the model.
- **Target Directory**: The working directory the harness (and the inner model) will operate in.
- **Output Artifacts**: Structured results including JSON, a human-readable report, and a ready-to-apply patch when changes are made.

See [output-artifacts.md](output-artifacts.md) for details on what gets produced.

## Common Flags

- `--model`: Which model to use (default: `grok-build`)
- `--timeout`: Maximum time for the inner run (default 30 minutes)
- `--wait-for-completion`: If the inner run times out, keep polling until it finishes
- `--quiet` / `-q`: Minimal output (useful for automation and agents)
- `--dry-run`: Preview the full prompt and expected artifacts without actually running

## Next Steps

- See the [CLI Reference](cli-reference.md) for every flag.
- See [For Agents and Sidecars](for-agents-and-sidecars.md) if you're integrating this into a larger system.
- See [Long-running and Background Tasks](../long-running-and-background-tasks.md) for handling work that exceeds normal timeouts.
