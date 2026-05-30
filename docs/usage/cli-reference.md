# CLI Reference

This page documents the `gcdh` command line interface.

## Basic Usage

```bash
gcdh --task "..." --target-dir /path/to/project [options]
```

## Required Arguments

| Flag              | Description                                      |
|-------------------|--------------------------------------------------|
| `--task`          | The coding task to perform (required)            |
| `--target-dir`    | Working directory for the task (required)        |

## Common Options

| Flag                        | Description                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| `--output-file`             | Write structured results to this path (strongly recommended)                |
| `--quiet`, `-q`             | Minimal output (only errors + final artifact paths)                         |
| `--verbose`, `-v`           | More detailed internal progress                                             |
| `--dry-run`                 | Preview prompt and expected behavior without executing                      |
| `--wait-for-completion`     | If the inner run times out, keep polling until it finishes                  |
| `--max-wait`                | Maximum seconds to wait when using `--wait-for-completion` (default: 7200)  |
| `--status`                  | Show status of background/long-running runs and exit                        |
| `--resume`                  | Resume waiting for a previous background run                                |
| `--run-name`                | Human-friendly name for this run (used in status files)                     |
| `--prune` [N]               | Prune old completed status files (default: 7 days)                          |
| `--reap-dead`               | Scan for silent runs (no heartbeat >5m) and mark them `crashed`. Use after reboots or wrapper deaths. |
| `--detach`                  | Launch in daemon mode (nohup+setsid). Survives terminal close. Unix-only. Logs to /dev/null — always pair with `--output-file`. |
| `--model`                   | Model to use (default depends on environment)                               |
| `--timeout`                 | Timeout for a single inner run in seconds (default: 1800)                   |
| `--max-turns`               | Maximum turns for the inner run (default: 60)                               |
| `--context`                 | Additional context for the task                                             |
| `--constraints`             | Hard constraints or requirements                                            |
| `--version`                 | Show version and exit                                                       |
| `--help`, `-h`              | Show help message                                                           |

## Important Notes

- Always use `--output-file` for any non-trivial task if you want the full set of review artifacts.
- Combine `--dry-run` with `--quiet` for the cleanest preview experience when driving from another agent.
- Use `--wait-for-completion` + `--max-wait` for tasks that may exceed normal timeouts.
- **Background resilience**: `.cdh-run-*.status` files (with `last_heartbeat_at`) provide the primary observability. Use `--status`, `--reap-dead`, and `--resume` for long-running work. See the [Operational Runbook](../operations/runbook-resilience.md) for monitoring, alerting, `--detach` production implications, and recovery procedures after reboots/OOM.
- `--reap-dead` and `--status` use a 300s silence threshold via `looks_dead()`. Long inner calls (>5 min) may temporarily appear dead until the next poll point; the companion monitor script supports optional PID checks to reduce false positives.

See the other pages in the `usage/` directory for higher-level guidance.
