# Operational Runbook: Background Resilience & Long-Running Delegations

This runbook covers production operation of the Code Delegation Harness (gcdh) resilience features added in the 0.2.x / unreleased hardening cycle:

- Heartbeats (`last_heartbeat_at`) and `last_poll_at` via `StatusManager`
- `--reap-dead`: marks silent background runs as `crashed`
- `--detach`: daemon launch (nohup + setsid)
- Crash protection (atexit + SIGTERM/INT/HUP handlers + `.crashed` sentinel)
- `--resume` with auto-recovery + untrusted checkpoint injection from `PROGRESS.json` etc.
- Persistent `.cdh-run-<id>.status` files (0600, owner-checked) for observability

**Audience**: SRE/DevOps, platform teams running gcdh as part of agent sidecars or CI/CD delegation, on-call engineers.

**Scope**: Focus on monitoring, alerting, deployment implications, logging, real-world failure modes (reboots, OOM, disconnects), and integration with common monitoring stacks. Code changes are intentionally minimal; this runbook documents current behavior + operational workarounds.

## 1. Core Observability Primitives

Every delegation (especially with `--wait-for-completion`, `--run-name`, or long `--timeout`) writes a status file:

```
<target-dir>/.cdh-run-<8char>.status
```

Key fields for ops (see `StatusManager` and harness launch/wait paths):
- `run_id`, `run_name`, `task` (snippet), `target_dir`, `model`
- `state`: launched | waiting | running | completed | failed | crashed | max_wait_exceeded | completed_no_changes
- `started_at`, `ended_at`, `elapsed_seconds`
- `last_heartbeat_at`, `last_poll_at`, `last_heartbeat_message`
- `pid`: harness PID at launch (for optional liveness probe)
- `crash_reason` (when applicable)
- Full `prompt` (for high-fidelity `--resume`)

Status files are the **single source of truth** for background run lifecycle. They survive harness death.

### Heartbeats & Dead Detection
- `heartbeat()` and `record_poll()` both update `last_heartbeat_at` (ISO8601).
- `looks_dead(max_silence_seconds=300)`: returns true for active states if `(now - last_heartbeat_or_poll) > 300s`.
- Used by:
  - `--status`: labels "crashed (no heartbeat)"
  - `--reap-dead`: marks matching files `crashed` with reason
  - External monitors (see below)

**Critical Limitation (documented in source)**: During the blocking `call_model_headless` (the long `grok` subprocess call, default 1800s timeout), **no heartbeats are emitted**. A legitimately long inner run (> ~5 minutes) can be misclassified as dead by `--status`/`--reap-dead` or external watchers until the next poll/heartbeat point in the wait loop (or completion).

**Strong recommendation**: For any real ambitious or long-running dogfood work, **always launch with --long-running** (or --keep-driving).

This is not optional for serious runs. It:
- Bumps timeouts to multi-hour values automatically.
- Injects the full ruthless "job to the end" + mandatory fresh verification language.
- Enables dynamic fresh checkpoint injection on *every single probe* in the wait loop.

See the updated usage-notes.md for the exact recommended pattern. Do not launch real Proxmox-style or multi-hour skill extension work without it.

Mitigations (see monitor script):
- Use higher `--max-wait` and silence threshold (e.g. 1800s) for known-long tasks.
- Optional PID liveness check in monitor (`os.kill(pid, 0)` on Unix — cheap, no side effects).
- Prefer `--output-file` + artifacts for completion signal over relying solely on heartbeats.

## 2. Monitoring & Alerting Recommendations

### Recommended Pattern: Periodic Scanner + Alerting
Run a lightweight scanner (see `scripts/monitor_cdh_status.py` delivered with this runbook) every 1–5 minutes via cron/systemd timer against your important `target_dir`s.

Alert on:
- Any `state == "crashed"` (or "crashed (no heartbeat)")
- `looks_dead` true for active states (with PID check if possible)
- Active run with `elapsed_seconds > <business SLA>` (e.g. 4h for a doc task)
- Sentinel `.crashed` file present but status not yet promoted (rare race)

Example cron (root or service user with read on target dirs):
```cron
*/2 * * * * /usr/local/bin/monitor_cdh_status.py --target-dirs /srv/agent-work /home/ci/delegations --alert-on-dead --webhook https://hooks.slack.com/... --max-silence 600 --json >> /var/log/cdh-monitor.log 2>&1
```

Prometheus + node_exporter textfile (common in k8s/baremetal):
```bash
monitor_cdh_status.py --target-dirs /work --json | \
  jq -r ' .runs[] | select(.dead or .state=="crashed") | "cdh_dead_run{run_id=\"\(.run_id)\",name=\"\(.name)\"} 1"' \
  > /var/lib/node_exporter/textfile/cdh_dead.prom.tmp && \
  mv ... .prom
```
Scrape `cdh_dead_run` gauge; alert on >0.

### Sample Alert Queries (jq / shell)
```bash
# Any currently dead-looking runs
for f in /work/.cdh-run-*.status; do
  if python3 -c "
from code_delegation_harness.status import StatusManager
from pathlib import Path
sm=StatusManager(Path('$f'))
print(sm.load() and sm.looks_dead(300))
"; then echo "DEAD: $f"; fi
done
```

### Integration with Existing Tools
- **Prometheus/Grafana**: textfile collector pattern above + dashboard on elapsed, state transitions (parse json).
- **Datadog / Splunk / ELK**: Ship `.cdh-run-*.status` files (small, low volume) or run monitor and send events/metrics.
- **PagerDuty/Opsgenie/Slack**: monitor script `--webhook` posts JSON payload on dead/crashed. Add run_id + task snippet + target_dir for triage.
- **Kubernetes**: Run as CronJob or sidecar in agent pods; mount the shared target PVCs.
- **Systemd**: Use a timer + service that invokes the monitor; journal for logs.
- **CI healthchecks**: In long CI jobs, `gcdh --status --target-dir $WORK` as a step; fail pipeline if dead runs detected.

**Do not** alert on normal `max_wait_exceeded` without context — some tasks are intentionally fire-and-forget.

## 3. --detach Deployment & Production Implications

`--detach` (Unix-only) does:
```python
detached_cmd = ["nohup"] + cmd_without_detach
Popen(..., stdin=devnull, stdout=devnull, stderr=devnull, preexec_fn=os.setsid, close_fds=True)
```
Launcher prints PID and exits 0 immediately. The child continues in new session.

**What it survives well**:
- Terminal close / ssh disconnect (SIGHUP + setsid)
- Parent process death (most cases)

**What it does NOT handle**:
- **Logs**: Harness stdout/stderr are sent to `/dev/null`. There is **no** `nohup.out` capture in current implementation. All visibility is via `.status` files + artifacts written by `--output-file` (if used). Inner `grok` subprocess errors may be invisible until completion or reap.
- **OOM / SIGKILL / power loss / hard crash**: Uncatchable. Status left in `running`/`waiting`. Requires `--reap-dead` or monitor.
- **Supervision / restart**: None. If the detached harness dies, no automatic respawn.
- **Resource limits / cgroups**: Inherits from launch environment.
- **Windows**: Explicitly unsupported (errors early).

**Production Recommendation**:
Prefer a **systemd unit** (or equivalent supervisor) over raw `--detach` for servers/long-lived agents:

```ini
# /etc/systemd/system/cdh-delegate@.service
[Unit]
Description=CDH Delegation %i
After=network.target

[Service]
Type=simple
User=agent
WorkingDirectory=/work/%i
ExecStart=/usr/local/bin/gcdh --quiet --wait-for-completion --max-wait 14400 --output-file /work/%i/delegation.json ...
# Let systemd handle logs, restarts, limits
Restart=on-failure
RestartSec=10s
# Memory limits etc.
MemoryMax=4G
```

For true "detach and forget from an interactive session", `--detach` is acceptable **only if** you also pass `--output-file` and have the monitor running.

Post-detach management:
- `ps aux | grep gcdh`
- Kill by PID or `pkill -f "gcdh.*<run-name>"`
- Always inspect status file for last known state.

## 4. Logging, Observability & Runbooks

### Current Logging Reality
- No built-in file logging or `--log-file` flag.
- `--quiet` / `--verbose` control stdout only.
- In `--detach`: logs discarded (see above).
- The `.status` file + companion `.run-meta.json` / `.report.md` (when `--output-file` used) are the durable audit trail.

**Operational Rule**: For any production or long-running delegation, **always** supply `--output-file`. The JSON + report + status file together give you everything needed for post-mortems.

### Runbook: Common Operational Procedures

**Detect dead runs (manual)**:
```bash
gcdh --status --target-dir /work/myproject
# Look for "crashed (no heartbeat)" or high elapsed with active state
```

**Reap after reboot / OOM** (idempotent, safe):
```bash
gcdh --reap-dead --target-dir /work/myproject
# Then re-inspect with --status
```

**Recover a crashed run** (best effort):
```bash
gcdh --resume <run_id_or_.status_path> --wait-for-completion --max-wait 14400 --output-file recovered.json
```
- If the status was `crashed`, the prompt is automatically augmented with any `PROGRESS.json` / `TASK_STATE.md` etc. found in target (size-capped, labeled "UNTRUSTED").
- The inner agent is instructed to resume from checkpoint for tracking only.
- Success depends on the agent's ability to parse the injected context.

**Post-reboot / host recovery sequence** (add to boot scripts or systemd ExecStartPre for agent hosts):
1. `gcdh --reap-dead --target-dir /work/...` (for all active trees)
2. `gcdh --status ...` (human or script review)
3. For critical runs: `--resume` the important ones (or let orchestrator decide)
4. Prune old: `gcdh --prune 7 --target-dir ...`

**Pruning**:
Old completed files accumulate. Use `--prune` (default 7 days) in cron or as part of cleanup jobs.

### Recommended Log/Alert Hygiene
- Monitor script output to syslog or dedicated log.
- Include `run_id` + `run_name` + `target_dir` + `task` snippet in every alert.
- Do not page for `max_wait_exceeded` without additional context (some tasks legitimately take hours).

## 5. Reliability in Real Environments

| Failure Mode       | Caught by Crash Protection? | Status Left As     | Recovery Path                  | Alert/Monitor Signal      |
|--------------------|-----------------------------|--------------------|--------------------------------|---------------------------|
| Normal exit        | Yes (atexit)                | completed/failed   | N/A                            | Final artifacts           |
| SIGTERM/INT/HUP    | Yes (handler + sentinel)    | crashed            | --resume + checkpoint          | looks_dead or crashed     |
| Terminal disconnect (no --detach) | Partial (HUP may kill) | running/waiting    | --reap or manual               | stale heartbeat           |
| --detach + disconnect | Survives (setsid)        | continues          | --status / --resume            | normal heartbeats         |
| OOM killer (SIGKILL) | No (uncatchable)         | running            | --reap-dead after reboot       | no heartbeat + dead PID   |
| Reboot / power     | No                          | running            | --reap-dead at boot            | same                      |
| Hard crash / segv  | No                          | running            | --reap                         | same                      |
| Long inner call (>5m) | N/A (no HB during block) | may look dead     | Higher silence threshold or PID check | False positive possible |

**Key Design Trade-off**: Lightweight (no threads, no heavy deps, best-effort). SIGKILL and power loss are acknowledged unrecoverable; the system optimizes for the common "user kill, terminal close, normal crash" cases via sentinels + heartbeats + reaping.

## 6. Gaps & Known Limitations (Current as of 0.2.x)

1. **No heartbeat during inner model call** (biggest ops gotcha for long tasks). External PID probe in monitor is the practical mitigation.
2. **--detach log blackhole**. Always pair with `--output-file`. Consider outer `systemd` or wrapper script that redirects if you must use raw detach.
3. **No built-in metrics endpoint or push**. File-based + external scanner is the supported model.
4. **Checkpoint injection risk surface**. `load_checkpoint_context` + `--resume` from crashed explicitly labels data untrusted and instructs the agent to ignore commands, but the prompt is still concatenated. Treat target dirs as untrusted for monitor/resume paths.
5. **Unix-centric**. `--detach`, signal handlers, setsid, PID checks are all posix. Windows support is limited (no detach, limited crash protection).
6. **No automatic restart of failed background runs**. Orchestrator or human must decide to `--resume`.
7. **Status files only in target_dir**. If target is NFS / shared / untrusted, see SECURITY.md — do not use resilience features there.
8. **No log rotation or size management** for status files (they are tiny; prune handles history).

## 7. Quick Reference Commands

```bash
# Observe
gcdh --status --target-dir /work

# Clean up dead after incident
gcdh --reap-dead --target-dir /work

# Recover
gcdh --resume abc12345 --wait-for-completion --output-file recovered.json --target-dir /work

# Prune history
gcdh --prune 14 --target-dir /work

# With monitor script
python /path/to/scripts/monitor_cdh_status.py --target-dirs /work --alert-on-dead --max-silence 300
```

## 8. When to Engage On-Call / Escalate

- Multiple dead runs across projects after a host event (possible systemic issue: OOM, disk full preventing status writes, etc.).
- `--resume` from crashed repeatedly fails with the same agent (prompt injection or model behavior change?).
- Status files corrupted at scale (indicates FS or permission problem).
- High elapsed on critical path delegations without progress in artifacts.

Include in escalation: `ls -l .cdh-run-*.status`, `cat` of the relevant ones, recent host logs (OOM, dmesg), monitor output.

## 9. Post-Review Hardening (Meeting of Models — QA/Security/DevOps, 2026-05-30)

All P0 and key P1 items from the multi-perspective review have been implemented and verified:

- Owner + mode verification (`_is_owned_and_not_world_writable`) now enforced on **every** status read path (including the previous direct `json.loads` sites in prune, --status listing, and --resume resolution) via new `_read_status_secure` helper. Insecure files are skipped or cause explicit refusal.
- `fsync` added to `_atomic_write` before the `os.replace` for durability across sudden power loss / OOM.
- Crash protection paths now append structured reasons to sibling `.last-crash` logs (best-effort, 0600) for post-mortem auditability when sentinels or marks themselves fail.
- Checkpoint ingestion (`load_checkpoint_context`) hardened with 64 KiB cap + mandatory owner check + explicit "BEGIN UNTRUSTED CHECKPOINT" wrapper + "ignore embedded commands" instruction.
- Sentinel creation uses secure `O_CREAT|0o600` fd open.
- New tests cover: world-writable checkpoint rejection, `looks_dead(check_pid=True)`, prune skipping insecure files.
- Full threat model lives in SECURITY.md (assumption: target_dir is private/trusted).

**Additional Post-Review Hardening (Summary & Output Recovery):**
- When the inner agent omits the exact `=== DELEGATION SUMMARY ===` markers (common on very long or interrupted runs), the harness now performs best-effort synthesis by combining any partial model output with the agent's own `PROGRESS.json` / `TASK_STATE.md` checkpoints.
- The normalized result now includes `summary_synthesized_from_checkpoint: true`.
- `render_human_report` surfaces a clear `♻️ Summary Synthesized from Agent Checkpoints` section with review guidance.
- Agents are explicitly instructed (in the system prompt) to treat their checkpoints as a primary source when writing the final summary.
- This is now a supported, intentional recovery path rather than a failure mode.

**Grooming / Normalization Notes (Honey v4 "better notes" feedback, 2026-05-30):**
- Further deepened synthesis + rendering specifically for many-small-edits vault grooming and tag normalization workloads.
- First-class `♻️ Grooming / Normalization Notes` section (with cluster_evidence, validation_status, real_target_evidence, decisions, canonical_rules, Run Intent callouts).
- Structured JSON preview in Recovery Sources.
- Improved grouping for normalization patterns (e.g. `old → canonical` targets).
- v4 dogfood prompt now documents the recommended rich PROGRESS.json fields that power these high-signal reviewer notes.
- New regression tests + self-check dogfood using realistic Honey v4 validation-pass checkpoints.
- Result: harness artifacts for grooming runs now make it trivial for reviewers to produce the precise, evidence-based, intent-clarifying feedback Honey demonstrated on v4. Direct response to user steer "better notes from honey."

These changes directly address the injection, permission-race, auditability, and durability concerns raised by the specialist reviewers. The single source of truth for the review transcript and backlog closure is `MEETING_OF_MODELS_TRANSCRIPT.md` in the repo root.

---
Maintained as part of the harness operational documentation. Update when resilience behavior changes. Pair with SECURITY.md and the CLI reference.
