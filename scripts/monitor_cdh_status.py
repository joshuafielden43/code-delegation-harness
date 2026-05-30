#!/usr/bin/env python3
"""
CDH Status Monitor - Operational scanner for Code Delegation Harness background runs.

Scans .cdh-run-*.status files in one or more target directories, detects dead/crashed
runs using the same heartbeat/looks_dead logic as the harness, and supports alerting.

Designed for cron, systemd timers, CI healthchecks, and integration with Prometheus
(textfile), Slack/Opsgenie (webhook), or other monitoring.

Usage (minimal):
  python3 scripts/monitor_cdh_status.py --target-dirs /work /home/agent/tasks --max-silence 300

  # Alert mode (non-zero exit + optional webhook POST on any dead/crashed)
  python3 scripts/monitor_cdh_status.py \
    --target-dirs /srv/cdh-work \
    --alert-on-dead \
    --max-silence 600 \
    --webhook https://hooks.slack.com/services/XXX/YYY/ZZZ \
    --json

  # With PID liveness probe (Unix only; reduces false positives for long inner calls)
  python3 scripts/monitor_cdh_status.py --target-dirs . --pid-check --max-silence 300

Cron example (every 2 min):
  */2 * * * * cd /opt/cdh && python3 scripts/monitor_cdh_status.py \
    --target-dirs /work/delegations --alert-on-dead --max-silence 300 \
    --webhook "$SLACK_WEBHOOK" >> /var/log/cdh-monitor.log 2>&1

Prometheus node_exporter textfile (in a timer):
  python3 ... --json | jq -r '
    .runs[] | select(.dead or .state == "crashed") |
    "cdh_dead_run{run_id=\"\(.run_id)\",name=\"\(.name)\",target=\"\(.target_dir)\"} 1"
  ' > /var/lib/node_exporter/textfile/cdh.prom.tmp && mv ... .prom

The script prefers to import StatusManager.looks_dead from an installed or src
code_delegation_harness package for exact parity. If unavailable it falls back to
a minimal self-contained implementation (same algorithm).

Exit codes:
  0: No dead/crashed runs found (or only completed/failed)
  1: One or more dead or crashed runs detected (when --alert-on-dead used, or always in some modes)
  2: Usage / arg error

Security: Only reads status files (same trust model as `gcdh --status`). Does not
write or execute anything in target dirs. Still respect SECURITY.md: do not run
against untrusted/shared target directories where status files could be tampered.

Part of the code-delegation-harness operational toolkit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# --- Optional: use the real StatusManager for exact parity ---
_STATUS_MANAGER_AVAILABLE = False
try:
    # Common dev layout: PYTHONPATH=src or installed package
    from code_delegation_harness.status import StatusManager  # type: ignore
    _STATUS_MANAGER_AVAILABLE = True
except Exception:
    StatusManager = None  # type: ignore

# Fallback minimal implementation (kept in sync with status.py:looks_dead + record_poll/heartbeat)
def _looks_dead_fallback(data: dict[str, Any], max_silence_seconds: int = 300) -> bool:
    state = data.get("state")
    if state not in ("running", "waiting", "launched"):
        return False
    last = data.get("last_heartbeat_at") or data.get("last_poll_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00") if last.endswith("Z") else last)
        age = (datetime.now() - last_dt.replace(tzinfo=None)).total_seconds()
        return age > max_silence_seconds
    except Exception:
        return False


def _pid_alive(pid: int) -> bool:
    """Cheap Unix liveness check. Returns False on Windows or if process gone."""
    if os.name != "posix":
        return True  # cannot reliably probe on Windows; assume alive
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def scan_target(target_dir: str, max_silence: int, pid_check: bool) -> list[dict[str, Any]]:
    """Return list of interesting run dicts for one target_dir."""
    runs: list[dict[str, Any]] = []
    tpath = Path(target_dir).expanduser().resolve()
    if not tpath.exists():
        return runs

    for sf in sorted(tpath.glob(".cdh-run-*.status")):
        try:
            raw = sf.read_text()
            data = json.loads(raw)
        except Exception:
            runs.append({
                "file": sf.name,
                "target_dir": str(tpath),
                "state": "unreadable",
                "error": "json or read failed",
            })
            continue

        state = data.get("state", "unknown")
        run_id = data.get("run_id") or sf.stem.replace(".cdh-run-", "")
        name = data.get("run_name") or run_id
        pid = data.get("pid")

        dead = False
        reason = None

        if _STATUS_MANAGER_AVAILABLE and StatusManager is not None:
            try:
                sm = StatusManager(sf)
                if sm.load(require_owner_and_secure=False):  # monitor is read-only observer
                    dead = sm.looks_dead(max_silence_seconds=max_silence)
                    if dead:
                        reason = f"no heartbeat >{max_silence}s (via StatusManager)"
            except Exception:
                dead = _looks_dead_fallback(data, max_silence)
                if dead:
                    reason = f"no heartbeat >{max_silence}s (fallback)"
        else:
            dead = _looks_dead_fallback(data, max_silence)
            if dead:
                reason = f"no heartbeat >{max_silence}s (fallback)"

        # Optional PID probe to suppress false positive on long-running inner calls
        pid_dead = False
        if pid_check and isinstance(pid, int) and dead:
            if not _pid_alive(pid):
                pid_dead = True
                reason = (reason or "") + " + PID not alive"

        entry = {
            "file": sf.name,
            "run_id": run_id,
            "name": name,
            "state": state,
            "target_dir": str(tpath),
            "started_at": data.get("started_at"),
            "elapsed_seconds": data.get("elapsed_seconds"),
            "last_heartbeat_at": data.get("last_heartbeat_at") or data.get("last_poll_at"),
            "pid": pid,
            "task": (data.get("task") or "")[:80].replace("\n", " "),
            "dead": bool(dead),
            "dead_reason": reason if dead else None,
            "pid_dead": pid_dead,
        }
        if state in ("crashed", "crashed (no heartbeat)"):
            entry["crashed"] = True
            entry["crash_reason"] = data.get("crash_reason")
        runs.append(entry)
    return runs


def post_webhook(url: str, payload: dict[str, Any], timeout: int = 10) -> bool:
    """Fire-and-forget POST of JSON. Returns True on 2xx."""
    try:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "cdh-monitor/1.0"},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (URLError, HTTPError, OSError, TimeoutError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scan CDH .status files for dead/crashed background runs and alert.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See module docstring for full cron/webhook/Prometheus examples."
    )
    ap.add_argument("--target-dirs", nargs="+", required=True,
                    help="One or more directories containing .cdh-run-*.status files (absolute or ~ ok)")
    ap.add_argument("--max-silence", type=int, default=300,
                    help="Seconds of heartbeat silence before considering a run dead (default: 300)")
    ap.add_argument("--pid-check", action="store_true",
                    help="On Unix, also probe recorded PID with os.kill(pid,0); suppresses some false positives for long inner calls")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON summary to stdout (useful for jq / Prometheus)")
    ap.add_argument("--alert-on-dead", action="store_true",
                    help="Exit non-zero if any dead or crashed run found; also enables webhook if provided")
    ap.add_argument("--webhook", default=None,
                    help="Optional webhook URL; POSTs JSON payload when dead/crashed runs are found (and --alert-on-dead)")
    ap.add_argument("--quiet", "-q", action="store_true",
                    help="Minimal output (errors + final count only)")
    args = ap.parse_args()

    all_runs: list[dict[str, Any]] = []
    for td in args.target_dirs:
        all_runs.extend(scan_target(td, args.max_silence, args.pid_check))

    dead_or_crashed = [r for r in all_runs if r.get("dead") or r.get("crashed") or r.get("state") == "crashed"]
    summary = {
        "scanned_at": datetime.utcnow().isoformat() + "Z",
        "target_dirs": args.target_dirs,
        "max_silence": args.max_silence,
        "pid_check": args.pid_check,
        "total_runs": len(all_runs),
        "dead_or_crashed_count": len(dead_or_crashed),
        "runs": all_runs,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        if not args.quiet:
            print(f"[cdh-monitor] Scanned {len(args.target_dirs)} dir(s), {len(all_runs)} status files, max_silence={args.max_silence}s")
        if dead_or_crashed:
            print(f"[cdh-monitor] DETECTED {len(dead_or_crashed)} dead/crashed run(s):")
            for r in dead_or_crashed:
                label = "DEAD" if r.get("dead") else "CRASHED"
                print(f"  {label}: {r['file']} | {r.get('name')} | state={r.get('state')} | {r.get('dead_reason') or r.get('crash_reason','')}")
        elif not args.quiet:
            print("[cdh-monitor] All clear (no dead or crashed runs)")

    # Alert side effects
    alerted = False
    if args.alert_on_dead and dead_or_crashed:
        if args.webhook:
            payload = {
                "alert": "cdh_dead_or_crashed_runs",
                "count": len(dead_or_crashed),
                "scanned_at": summary["scanned_at"],
                "runs": [{"run_id": r["run_id"], "name": r["name"], "state": r["state"],
                          "target_dir": r["target_dir"], "reason": r.get("dead_reason") or r.get("crash_reason")}
                         for r in dead_or_crashed],
            }
            ok = post_webhook(args.webhook, payload)
            if not ok and not args.quiet:
                print("[cdh-monitor] WARNING: webhook POST failed (network or endpoint issue)", file=sys.stderr)
            alerted = True
        # Always non-zero when --alert-on-dead and problems found
        return 1

    return 0 if not (args.alert_on_dead and dead_or_crashed) else 1


if __name__ == "__main__":
    sys.exit(main())
