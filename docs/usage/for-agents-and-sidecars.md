# For Agents and Sidecars

The Code Delegation Harness was explicitly designed to be driven by other agents and autonomous systems, not just humans.

## Core Design Principles for Agents

- **Minimal output by default** — Use `--quiet` (`-q`) so the harness only emits errors and final artifact paths. This is ideal for programmatic consumption.
- **Stable, structured output** — The primary artifact is always a JSON file with a consistent schema.
- **Full observability for long-running work** — Use `--wait-for-completion`, `--status`, and `--resume` so your agent can handle tasks that exceed single-turn timeouts.
- **Safe previewing** — `--dry-run` (especially combined with `--quiet`) lets agents cheaply validate scope before committing real work.
- **Clear separation of concerns** — The harness keeps implementation work isolated from the calling agent's memory and personality.

## Recommended Pattern for Agents

```bash
gcdh \
  --quiet \
  --task "..." \
  --target-dir /path/to/project \
  --output-file /tmp/delegation-$(date +%s).json \
  --wait-for-completion \
  --max-wait 14400
```

Then read the output JSON (and companion `.report.md` / `.patch` if they exist).

## Key Flags for Agent Use

- `--quiet` / `-q`
- `--output-file` (strongly recommended)
- `--dry-run`
- `--wait-for-completion` + `--max-wait`
- `--status` and `--resume` (for observability and recovery)
- `--run-name` (for human-friendly identification in status files)

## Status Files as a Coordination Mechanism

When using `--wait-for-completion` or `--run-name`, the harness writes persistent `.cdh-run-*.status` files. These can be used by orchestrating agents to:

- Detect in-progress delegations
- Resume waiting after restarts
- Surface work to humans via `--status`

## Anti-Patterns to Avoid

- Do not rely on the harness to maintain long-term memory or personality for your agent.
- Do not treat the inner model's responses as authoritative without going through the review artifacts.
- Avoid running very large tasks without `--output-file` and proper status handling.

## Future Direction

This harness is intended to serve as both a human tool *and* as infrastructure for future dedicated sidecar architectures. The output formats, status system, and separation of concerns are all designed with that dual use in mind.
