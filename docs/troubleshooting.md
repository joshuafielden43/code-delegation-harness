# Troubleshooting

## Common Issues

### "Required status check 'CI' is expected" when trying to push

This usually means branch protection is configured to require a pull request. You cannot push directly to `main`.

**Solution**: Create a branch, push it, open a PR, then merge (using admin rights if you're the owner and CI is green).

### Inner run keeps timing out

Increase `--timeout` and/or use `--wait-for-completion --max-wait`.

### The generated patch doesn't apply cleanly

This can happen if the target directory has diverged since the delegation started. Review the actual changes in the working directory rather than blindly applying the patch.

### Import errors in tests after renaming / packaging changes

The test suite has some legacy import hacks from the rename to `code_delegation_harness`. Run tests with `python -m pytest` after `pip install -e .` for the most reliable results.

## Background / Long-Running Resilience Issues

### Runs appear "dead" or stuck in "running" after reboot / OOM / kill -9
The harness cannot catch SIGKILL, OOM killer, power loss, or hard crashes. Status files are left in the last state.

**Resolution**:
```bash
gcdh --reap-dead --target-dir /path/to/work
gcdh --status --target-dir /path/to/work
```
Then use `--resume <id>` for critical runs (it will inject any `PROGRESS.json` checkpoints found).

Add `gcdh --reap-dead ...` to boot scripts or systemd `ExecStartPre` for hosts running delegations.

### False "dead" for legitimately long tasks
During the inner model call (which can be 30+ minutes), the harness does not emit heartbeats. `--status` / `--reap-dead` or external monitors using the default 300s threshold may flag it.

**Workarounds**:
- Pass a higher `--max-wait` and use the operational monitor script with `--max-silence 1800 --pid-check`.
- Check the companion artifacts (`.report.md`, status `elapsed_seconds`) rather than relying only on heartbeat age.
- See the [Operational Runbook](../operations/runbook-resilience.md) for PID liveness probe pattern.

### --detach produces no visible logs
By design, `--detach` redirects all harness stdout/stderr to `/dev/null`. The only durable signals are the `.status` file and artifacts from `--output-file`.

**Always** use `--output-file` with `--detach`. For production servers, prefer a systemd unit (which can capture logs and supervise) over raw `--detach`.

## Getting Help

- Check the [CLI Reference](usage/cli-reference.md)
- Review the [Operational Runbook](../operations/runbook-resilience.md) for monitoring, alerting, and recovery runbooks
- Review [For Agents and Sidecars](usage/for-agents-and-sidecars.md) if you're building on top of this
- Open an issue with as much context as possible (command used, error output, target directory state)
