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
        self._data["last_poll_at"] = datetime.now().isoformat()
        if error:
            self._data["last_poll_error"] = error[:500]
        # Throttled write happens in caller for now (keeps this lightweight)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

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
