"""
Lightweight status management for long-running and background delegations.

Centralizes creation, writing, reading, and recovery of status files
to make the system more resilient and easier to reason about.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


class StatusManager:
    """
    Manages the lifecycle of delegate run status files.

    Goals:
    - Atomic and secure writes (0600 permissions)
    - Easy recovery and resumption
    - Clear state machine
    - Lightweight (minimal dependencies, fast operations)
    """

    VALID_STATES = {
        "launched",
        "waiting",
        "running",
        "completed",
        "completed_no_changes",
        "failed",
        "crashed",          # New: detected dead background run
        "max_wait_exceeded",
    }

    def __init__(self, status_file: Path):
        self.status_file = Path(status_file)
        self._data: dict[str, Any] = {}

    @classmethod
    def create_new(
        cls,
        run_id: str,
        run_name: Optional[str],
        task: Optional[str],
        target_dir: str,
        model: str,
        state: str = "launched",
        prompt: Optional[str] = None,
        context: Optional[str] = None,
        constraints: Optional[str] = None,
    ) -> StatusManager:
        """Factory for a brand new status record at launch time."""
        manager = cls(Path(target_dir) / f".cdh-run-{run_id}.status")

        task_snippet = ((task or "")[:140].replace("\n", " ").strip() + "...") if task else ""

        data = {
            "run_id": run_id,
            "run_name": run_name,
            "task": task_snippet,
            "target_dir": target_dir,
            "model": model,
            "state": state,
            "started_at": datetime.now().isoformat(),
            "elapsed_seconds": 0,
            "last_poll_at": None,
            "pid": os.getpid(),
        }

        if prompt:
            data["prompt"] = prompt
        if context:
            data["context"] = context
        if constraints:
            data["constraints"] = constraints

        manager._data = data
        manager._atomic_write()
        return manager

    def load(self) -> bool:
        """Load existing status from disk. Returns True on success.

        Attempts best-effort recovery if the file is partially corrupted.
        """
        if not self.status_file.exists():
            return False
        try:
            raw = self.status_file.read_text()
            self._data = json.loads(raw)
            return True
        except json.JSONDecodeError:
            # Try to recover whatever we can (very defensive for long-running recovery)
            try:
                self._data = {"_corrupted": True, "raw": raw[:2000]}
            except Exception:
                self._data = {"_corrupted": True}
            return False
        except Exception:
            self._data = {"_corrupted": True}
            return False

    def load_or_recover(self, fallback_data: Optional[dict] = None) -> bool:
        """Load if possible, otherwise start with fallback data (or empty)."""
        if self.load():
            return True
        self._data = fallback_data or {"_recovered": True, "state": "waiting"}
        return False

    def ensure_recoverable(self, run_id: str, run_name: Optional[str], cwd: str, model: str) -> None:
        """
        Self-healing for long-running resilience.

        If the status is corrupted or missing critical fields (run_id, target_dir, state, model),
        repair it with the caller-supplied context so --resume and wait loops can still function.
        Never loses existing good data; only fills gaps.
        """
        dirty = False
        if not self._data:
            self._data = {}
            dirty = True

        if self._data.get("_corrupted") or not self._data.get("run_id"):
            self._data["run_id"] = run_id
            dirty = True
        if not self._data.get("target_dir"):
            self._data["target_dir"] = cwd
            dirty = True
        if not self._data.get("model"):
            self._data["model"] = model
            dirty = True
        if not self._data.get("state"):
            self._data["state"] = "waiting"
            dirty = True
        if run_name and not self._data.get("run_name"):
            self._data["run_name"] = run_name
            dirty = True

        # Mark recovery for auditability without overwriting a real prompt/task if present
        if self._data.get("_corrupted") or self._data.get("_recovered") is None:
            if "_recovered" not in self._data:
                self._data["_recovered"] = True
            dirty = True

        if dirty:
            self._atomic_write()

    def update(self, **kwargs: Any) -> None:
        """Update fields and persist."""
        self._data.update(kwargs)
        self._atomic_write()

    def set_state(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid status state: {state}")
        self._data["state"] = state
        self._data["last_poll_at"] = datetime.now().isoformat()
        self._atomic_write()

    def mark_completed(self, exit_code: int, final_status: Optional[str] = None) -> None:
        self._data["state"] = "completed" if exit_code in (0, None) else "failed"
        if final_status:
            self._data["final_status"] = final_status
        else:
            self._data["final_status"] = "success" if exit_code in (0, None) else "failure_or_partial"
        self._data["final_exit_code"] = exit_code
        self._data["ended_at"] = datetime.now().isoformat()
        self._atomic_write()

    def mark_max_wait_exceeded(self, elapsed: float) -> None:
        self._data["state"] = "max_wait_exceeded"
        self._data["elapsed_seconds"] = int(elapsed)
        self._data["ended_at"] = datetime.now().isoformat()
        self._atomic_write()

    def record_poll(self, elapsed: float, error: Optional[str] = None) -> None:
        self._data["elapsed_seconds"] = int(elapsed)
        now = datetime.now().isoformat()
        self._data["last_poll_at"] = now
        self._data["last_heartbeat_at"] = now  # Treat poll as a heartbeat
        if error:
            self._data["last_poll_error"] = error[:500]
        # Throttled write happens in caller for now (keeps this lightweight)

    def heartbeat(self, message: str = "") -> None:
        """Write an explicit heartbeat. Call this from long-running inner loops
        or from the harness wrapper to prove the process is still alive.
        """
        now = datetime.now().isoformat()
        self._data["last_heartbeat_at"] = now
        if message:
            self._data["last_heartbeat_message"] = message[:200]
        # Use the throttled path if available, otherwise direct write
        try:
            self._atomic_write()
        except Exception:
            pass

    def mark_crashed(self, reason: str = "No heartbeat detected for extended period - background run appears dead") -> None:
        """Mark this run as crashed. Useful for recovery logic when a
        background task dies without properly writing a failed/completed state.
        """
        self._data["state"] = "crashed"
        self._data["crashed_at"] = datetime.now().isoformat()
        self._data["crash_reason"] = reason
        self._atomic_write()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def looks_dead(self, max_silence_seconds: int = 300) -> bool:
        """Returns True if this run is in a 'running' or 'waiting' state but
        has had no heartbeat/poll for longer than max_silence_seconds.
        Useful for external monitors or --status to flag crashed background tasks.
        """
        state = self._data.get("state")
        if state not in ("running", "waiting", "launched"):
            return False

        last = self._data.get("last_heartbeat_at") or self._data.get("last_poll_at")
        if not last:
            return False

        try:
            last_dt = datetime.fromisoformat(last)
            age = (datetime.now() - last_dt).total_seconds()
            return age > max_silence_seconds
        except Exception:
            return False

    def write(self) -> None:
        """Force write current state."""
        self._atomic_write()

    def _atomic_write(self) -> None:
        """Write atomically with secure permissions."""
        try:
            tmp_path = self.status_file.with_suffix(self.status_file.suffix + ".tmp")
            tmp_path.write_text(json.dumps(self._data, indent=2))
            os.replace(tmp_path, self.status_file)
            os.chmod(self.status_file, 0o600)
        except Exception:
            # Best effort — never let status writing crash the harness
            pass

    @property
    def state(self) -> str:
        return self._data.get("state", "unknown")

    @property
    def run_id(self) -> str:
        return self._data.get("run_id", "")


# --- Module-level crash protection support (used by harness launcher) ---
# Kept here for better encapsulation with the rest of the status machinery.
_ACTIVE_STATUS_FILE: Optional[Path] = None


def _mark_active_run_crashed(reason: str = "Harness process terminated unexpectedly") -> None:
    """Best-effort attempt to mark the current active run as crashed on exit/signal."""
    global _ACTIVE_STATUS_FILE
    if _ACTIVE_STATUS_FILE and _ACTIVE_STATUS_FILE.exists():
        try:
            sm = StatusManager(_ACTIVE_STATUS_FILE)
            if sm.load():
                current_state = sm.get("state", "")
                if current_state in ("launched", "waiting", "running"):
                    sm.mark_crashed(reason)
                    print(f"[cdh] Emergency: marked run as crashed on process exit ({reason})", file=sys.stderr)
        except Exception:
            pass
    _ACTIVE_STATUS_FILE = None


def register_crash_protection(status_file: Path) -> None:
    """Register atexit + signal handlers so we try to mark the run crashed if we die.
    This is the public entry point used by the harness.
    """
    global _ACTIVE_STATUS_FILE
    _ACTIVE_STATUS_FILE = Path(status_file)

    import atexit
    import signal as _signal
    import os as _os

    atexit.register(_mark_active_run_crashed, "Process exited (atexit)")

    def _signal_handler(signum, frame):
        _mark_active_run_crashed(f"Received signal {signum}")
        _signal.signal(signum, _signal.SIG_DFL)
        _os.kill(_os.getpid(), signum)

    for sig in (_signal.SIGTERM, _signal.SIGINT):
        try:
            _signal.signal(sig, _signal_handler)
        except (ValueError, OSError):
            pass
