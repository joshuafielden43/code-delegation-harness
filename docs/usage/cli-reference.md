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
| `--prune-research` [N]      | Prune research/tmp artifacts (traces, stdout/stderr) older than N days (default: 7). Use with `--research-dir` for non-default locations. |
| `--reap-dead`               | Scan for silent runs (no heartbeat >5m) and mark them `crashed`. Use after reboots or wrapper deaths. |
| `--detach`                  | Launch in daemon mode (nohup+setsid). Survives terminal close. Unix-only. Logs to /dev/null — always pair with `--output-file`. |
| `--long-running`, `--keep-driving` | Long-job mode with stronger timeouts/turns/wait defaults and hardened continuation behavior |
| `--auto-remediate`          | Enable automatic pass-2 remediation when pass-1 underperforms                |
| `--remediate-on`            | Comma-separated remediation triggers (`partial,fail,missing_summary`)         |
| `--iterations` N            | Total pass cap including original run (default: 2). Replaces/aliases `--remediation-max-passes`. |
| `--remediation-max-passes`  | Maximum remediation passes (default: `1`). Use `--iterations` for the PRD-aligned flag. |
| `--remediation-mode`        | Remediation strategy (currently: `targeted-inversion`)                        |
| `--model`                   | Execution CLI model to use (default: `grok-build`)                           |
| `--orchestrator-model`      | Model for intake normalization and attack frame generation (default: inherits `--model`) |
| `--orchestrator-provider`   | Orchestrator backend: `auto` (detect from env), `anthropic` (SDK), `cli` (reuse execution CLI). Default: `auto`. |
| `--orchestrator-timeout`    | Timeout in seconds for the intake orchestrator call (default: 30). Up to 3 retries on transient failure. |
| `--skip-normalization`      | Bypass intake detection, normalization, and stanza injection entirely. Pass raw prompt to CLI. |
| `--no-hygiene`              | Skip hygiene stanza injection only. Intake still runs. For debugging. |
| `--stanza-modules`          | Comma-separated hygiene stanza modules (default: `base`). |
| `--confirm`                 | Show normalized prompt + manifest before running. Max 2 correction rounds. Off by default. |
| `--research-dir`            | Directory for full stdout/stderr artifacts and build attempt traces. Default: `{target-dir}/research/tmp`. |
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
- `--auto-remediate` is opt-in: pass 2 only runs when pass 1 matches configured degraded triggers.
- In remediation mode, final JSON can include `pass_number`, `parent_run_id`, `remediation_reason`, `weakness_profile`, `remediation_applied`, and `remediation_delta`.
- With `--output-file`, remediation mode writes `<output-stem>.pass2.prompt.txt` for audit/review of the generated counter-prompt.

See the other pages in the `usage/` directory for higher-level guidance.
