"""
Lightweight status management for long-running and background delegations.

Centralizes creation, writing, reading, and recovery of status files
to make the system more resilient and easier to reason about.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


logger = logging.getLogger(__name__)


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
        self._lock = threading.RLock()

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
            "started_at": datetime.now(timezone.utc).isoformat(),
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

        with manager._lock:
            manager._data = data
            manager._atomic_write()
        return manager

    def load(self, require_owner_and_secure: bool = True) -> bool:
        """Load existing status from disk. Returns True on success.

        If require_owner_and_secure=True (default for control paths), verifies
        that the file is owned by the current user and has no group/other write bits.
        This mitigates tampering in shared target directories.

        Attempts best-effort recovery if the file is partially corrupted.
        """
        if self.status_file.is_symlink():
            with self._lock:
                self._data = {"_insecure": True, "reason": "symlink"}
            return False
        if not self.status_file.exists():
            return False

        if require_owner_and_secure:
            try:
                st = self.status_file.lstat()
                if st.st_uid != os.getuid():
                    with self._lock:
                        self._data = {"_insecure": True, "reason": "not owner"}
                    return False
                if st.st_mode & 0o022:
                    with self._lock:
                        self._data = {"_insecure": True, "reason": "world/group writable"}
                    return False
            except Exception:
                with self._lock:
                    self._data = {"_insecure": True, "reason": "stat failed"}
                return False

        # Check for lightweight crash sentinel written from signal/atexit handlers
        sentinel = self.status_file.with_suffix(self.status_file.suffix + ".crashed")
        if sentinel.exists():
            if sentinel.is_symlink():
                with self._lock:
                    self._data = {"_insecure": True, "reason": "symlink_sentinel"}
                return False
            try:
                if require_owner_and_secure:
                    st = sentinel.lstat()
                    if st.st_uid != os.getuid() or (st.st_mode & 0o022):
                        # Fail closed: insecure sentinel is not trusted (matches status file behavior)
                        with self._lock:
                            self._data = {"_insecure": True, "reason": "insecure_crash_sentinel"}
                        return False
                nof = getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(str(sentinel), os.O_RDONLY | nof)
                with os.fdopen(fd, "r", encoding="utf-8") as f:
                    reason = f.read().strip()
                with self._lock:
                    self._data = {"state": "crashed", "crash_reason": reason, "_from_sentinel": True}
                return True
            except Exception:
                pass

        try:
            nof = getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(str(self.status_file), os.O_RDONLY | nof)
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                raw = f.read()
            with self._lock:
                self._data = json.loads(raw)
            # Proactive cleanup: if we loaded a terminal non-crashed state, remove any stale sentinel
            if self._data.get("state") in ("completed", "failed", "max_wait_exceeded"):
                sentinel = self.status_file.with_suffix(self.status_file.suffix + ".crashed")
                if sentinel.exists() and not sentinel.is_symlink():
                    try:
                        sentinel.unlink()
                        logger.warning(f"[cdh] Cleaned stale crash sentinel for {self.status_file.name}")
                    except Exception:
                        pass
            return True
        except json.JSONDecodeError:
            # Try to recover whatever we can (very defensive for long-running recovery)
            try:
                with self._lock:
                    self._data = {"_corrupted": True, "raw": raw[:2000]}
            except Exception:
                with self._lock:
                    self._data = {"_corrupted": True}
            return False
        except Exception:
            with self._lock:
                self._data = {"_corrupted": True}
            return False

    def load_or_recover(self, fallback_data: Optional[dict] = None) -> bool:
        """Load if possible, otherwise start with fallback data (or empty)."""
        if self.load():
            return True
        with self._lock:
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
        with self._lock:
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
                # Clear transient corruption marker after successful healing so future
                # ensure_recoverable calls (e.g. during resume or status) do not re-clobber
                # caller-supplied values into an otherwise valid record.
                if "_corrupted" in self._data:
                    del self._data["_corrupted"]
                dirty = True

        if dirty:
            self._atomic_write()

    def update(self, **kwargs: Any) -> None:
        """Update fields and persist."""
        with self._lock:
            self._data.update(kwargs)
        self._atomic_write()

    def set_state(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid status state: {state}")
        with self._lock:
            self._data["state"] = state
            self._data["last_poll_at"] = datetime.now(timezone.utc).isoformat()
        self._atomic_write()

        # If we are moving to a terminal non-crashed state, clean any crash sentinel
        if state in ("completed", "failed", "completed_no_changes", "max_wait_exceeded"):
            self._cleanup_crash_sentinel()

    def mark_completed(self, exit_code: int, final_status: Optional[str] = None) -> None:
        with self._lock:
            self._data["state"] = "completed" if exit_code in (0, None) else "failed"
            if final_status:
                self._data["final_status"] = final_status
            else:
                self._data["final_status"] = "success" if exit_code in (0, None) else "failure_or_partial"
            self._data["final_exit_code"] = exit_code
            self._data["ended_at"] = datetime.now(timezone.utc).isoformat()
        self._atomic_write()
        self._cleanup_crash_sentinel()

    def mark_max_wait_exceeded(self, elapsed: float) -> None:
        with self._lock:
            self._data["state"] = "max_wait_exceeded"
            self._data["elapsed_seconds"] = int(elapsed)
            self._data["ended_at"] = datetime.now(timezone.utc).isoformat()
        self._atomic_write()
        self._cleanup_crash_sentinel()

    def record_poll(self, elapsed: float, error: Optional[str] = None) -> None:
        with self._lock:
            self._data["elapsed_seconds"] = int(elapsed)
            now = datetime.now(timezone.utc).isoformat()
            self._data["last_poll_at"] = now
            self._data["last_heartbeat_at"] = now  # Treat poll as a heartbeat
            if error:
                self._data["last_poll_error"] = error[:500]
        # Throttled write happens in caller for now (keeps this lightweight)

    def heartbeat(self, message: str = "") -> None:
        """Write an explicit heartbeat. Call this from long-running inner loops
        or from the harness wrapper to prove the process is still alive.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._data["last_heartbeat_at"] = now
            if message:
                self._data["last_heartbeat_message"] = message[:200]
        # Use the throttled path if available, otherwise direct write
        try:
            self._atomic_write()
        except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def mark_crashed(self, reason: str = "No heartbeat detected for extended period - background run appears dead") -> None:
        """Mark this run as crashed. Useful for recovery logic when a
        background task dies without properly writing a failed/completed state.
        """
        with self._lock:
            self._data["state"] = "crashed"
            self._data["crashed_at"] = datetime.now(timezone.utc).isoformat()
            self._data["crash_reason"] = reason
        self._atomic_write()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def looks_dead(self, max_silence_seconds: int = 300, check_pid: bool = False) -> bool:
        """Returns True if this run is in a 'running' or 'waiting' state but
        has had no heartbeat/poll for longer than max_silence_seconds.
        Useful for external monitors or --status to flag crashed background tasks.

        If check_pid=True (optional, cheap on Unix), also verifies that the recorded
        PID is still alive using os.kill(pid, 0). This greatly reduces false positives
        during long synchronous call_model_headless executions.
        """
        with self._lock:
            state = self._data.get("state")
            if state not in ("running", "waiting", "launched"):
                return False

            last = self._data.get("last_heartbeat_at") or self._data.get("last_poll_at")
            if not last:
                return False

            last_copy = last
            pid = self._data.get("pid")
        try:
            last_dt = datetime.fromisoformat(last_copy)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age <= max_silence_seconds:
                return False
        except Exception:
            return False

        if not check_pid:
            return True

        if not pid:
            return True  # No PID recorded → fall back to time-based only

        try:
            os.kill(pid, 0)  # Does not kill; just checks existence
            return False     # Process is still alive
        except (OSError, ProcessLookupError):
            return True      # Process is dead
        except Exception:
            return True      # Conservative: treat as dead on unexpected error

    def write(self) -> None:
        """Force write current state."""
        self._atomic_write()

    def _atomic_write(self) -> None:
        """Write atomically with secure permissions.
        Includes fsync for durability (P1 from DevOps/Security review) so that
        status and crash sentinels survive sudden power loss / OOM / hard kill
        between write and replace.
        """
        try:
            with self._lock:
                snap = dict(self._data)
            tmp_path = self.status_file.with_suffix(self.status_file.suffix + ".tmp")
            data = json.dumps(snap, indent=2).encode("utf-8")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            try:
                fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
                fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception:
                try:
                    os.unlink(str(tmp_path))
                except Exception:
                    pass
                raise
            try:
                dir_fd = os.open(str(tmp_path.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception:
                pass
            os.replace(tmp_path, self.status_file)
            try:
                dir_fd = os.open(str(self.status_file.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception:
                pass
        except Exception:
            pass

    def _cleanup_crash_sentinel(self) -> None:
        """Remove the lightweight crash sentinel if it exists.
        Called on successful completion to prevent stale 'crashed' state on future loads.
        """
        try:
            sentinel = self.status_file.with_suffix(self.status_file.suffix + ".crashed")
            if sentinel.exists() and not sentinel.is_symlink():
                sentinel.unlink()
        except Exception:
            pass

    @property
    def state(self) -> str:
        with self._lock:
            return self._data.get("state", "unknown")

    @property
    def run_id(self) -> str:
        with self._lock:
            return self._data.get("run_id", "")

    # --- Prompt audit trail surface (stabilization for long-running visibility + future Prompt IR) ---
    # These make every model prompt (especially long-running probes) a first-class durable
    # artifact observable via the .status file without extra fs walks. 0600 atomic via _atomic_write.

    def set_prompt_audit_dir(self, audit_dir: str) -> None:
        """Record the directory containing prompt audit artifacts for this run."""
        with self._lock:
            self._data["prompt_audit_dir"] = audit_dir
        self._atomic_write()

    def record_prompt_audit(self, label: str, prompt_file: str, meta_file: str) -> None:
        """Append a single prompt audit entry to the status for quick visibility.
        Keeps only the last 50 entries for sanity on very long-running runs.
        Never lets audit recording kill the harness.
        """
        try:
            with self._lock:
                audits = self._data.setdefault("prompt_audits", [])
                audits.append({
                    "label": label,
                    "prompt_file": prompt_file,
                    "meta_file": meta_file,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if len(audits) > 50:
                    self._data["prompt_audits"] = audits[-50:]
            self._atomic_write()
        except Exception:
            # Best effort — auditing must never break long-running resilience
            pass

    def get_prompt_audit_trail(self) -> list[dict]:
        """Return the list of prompt audits recorded for this run (from status)."""
        with self._lock:
            return self._data.get("prompt_audits", [])

    @property
    def prompt_audit_dir(self) -> Optional[str]:
        """Return the directory containing prompt audit artifacts for this run, if set."""
        with self._lock:
            return self._data.get("prompt_audit_dir")

    def get_latest_prompt_audit(self) -> Optional[dict]:
        """Return the most recent prompt audit entry, if any."""
        with self._lock:
            audits = self._data.get("prompt_audits", [])
            return audits[-1] if audits else None


# --- Module-level crash protection support (used by harness launcher) ---
# Kept here for better encapsulation with the rest of the status machinery.
_ACTIVE_STATUS_FILE: Optional[Path] = None


def _append_crash_log(status_file: Path, reason: str) -> None:
    """Best-effort append-only crash log next to a status file for auditability.
    Never raises; used to improve forensics in protection paths (P1 from Security review).
    """
    try:
        log_path = status_file.with_suffix(status_file.suffix + ".last-crash")
        if log_path.is_symlink():
            return
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts} | {reason}\n".encode("utf-8")
        fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            d_fd = os.open(str(log_path.parent), os.O_RDONLY)
            try:
                os.fsync(d_fd)
            finally:
                os.close(d_fd)
        except Exception:
            pass
    except Exception:
        pass  # absolute best effort


def _mark_active_run_crashed(reason: str = "Harness process terminated unexpectedly") -> None:
    """Best-effort attempt to mark the current active run as crashed on exit/signal.
    Now also appends to a .last-crash sibling log for post-mortem auditability
    when the primary mark or sentinel path itself fails.
    """
    global _ACTIVE_STATUS_FILE
    if _ACTIVE_STATUS_FILE and _ACTIVE_STATUS_FILE.exists():
        try:
            sm = StatusManager(_ACTIVE_STATUS_FILE)
            if sm.load():
                current_state = sm.get("state", "")
                if current_state in ("launched", "waiting", "running"):
                    sm.mark_crashed(reason)
                    logger.warning(f"[cdh] Emergency: marked run as crashed on process exit ({reason})")
                    _append_crash_log(_ACTIVE_STATUS_FILE, reason)

                    # Write lightweight sentinel *only on actual crash* (secure 0o600).
                    # This gives --reap-dead and load() a signal-context-safe marker even if
                    # the full status JSON write is racy or the process is hard-killed shortly after.
                    try:
                        import os as _os2
                        sentinel = _ACTIVE_STATUS_FILE.with_suffix(_ACTIVE_STATUS_FILE.suffix + ".crashed")
                        tmp_s = sentinel.with_suffix(sentinel.suffix + ".tmp")
                        try:
                            if tmp_s.exists():
                                tmp_s.unlink()
                        except Exception:
                            pass
                        try:
                            fd = _os2.open(str(tmp_s), _os2.O_WRONLY | _os2.O_CREAT | _os2.O_EXCL, 0o600)
                        except FileExistsError:
                            try:
                                if tmp_s.exists():
                                    tmp_s.unlink()
                            except Exception:
                                pass
                            fd = _os2.open(str(tmp_s), _os2.O_WRONLY | _os2.O_CREAT | _os2.O_EXCL, 0o600)
                        try:
                            with _os2.fdopen(fd, "w") as f:
                                f.write(f"reason: {reason}\nat: {datetime.now(timezone.utc).isoformat()}\n")
                                f.flush()
                                _os2.fsync(f.fileno())
                        except Exception:
                            try:
                                _os2.unlink(str(tmp_s))
                            except Exception:
                                pass
                            raise
                        try:
                            d_fd = _os2.open(str(tmp_s.parent), _os2.O_RDONLY)
                            try:
                                _os2.fsync(d_fd)
                            finally:
                                _os2.close(d_fd)
                        except Exception:
                            pass
                        _os2.replace(str(tmp_s), str(sentinel))
                        try:
                            d_fd = _os2.open(str(sentinel.parent), _os2.O_RDONLY)
                            try:
                                _os2.fsync(d_fd)
                            finally:
                                _os2.close(d_fd)
                        except Exception:
                            pass
                    except Exception as se:
                        _append_crash_log(_ACTIVE_STATUS_FILE, f"SENTINEL_WRITE_ON_CRASH_FAILED: {se}")
        except Exception as e:
            # Record the protection failure itself for forensics
            _append_crash_log(_ACTIVE_STATUS_FILE, f"PROTECTION_FAILURE: {e} (original reason: {reason})")
            pass
    _ACTIVE_STATUS_FILE = None


def register_crash_protection(status_file: Path) -> None:
    """Register atexit + signal handlers so we try to mark the run crashed if we die.
    This is the public entry point used by the harness.

    LIMITATIONS (known, by design for lightweight):
    - SIGKILL / OOM killer / power loss / hard crash: cannot be caught; status may stay "running".
      Use --reap-dead or external monitors + looks_dead() for those cases.
    - Unix signals only (SIGTERM/INT + atexit). On Windows these are no-ops or limited;
      detach mode also Unix-only (nohup/setsid in harness).
    - Best-effort only; write errors swallowed.
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

    for sig in (_signal.SIGTERM, _signal.SIGINT, _signal.SIGHUP):
        try:
            _signal.signal(sig, _signal_handler)
        except (ValueError, OSError):
            pass

    # Sentinel is now created *only* on actual crash paths (see _mark_active_run_crashed).
    # Writing it here at registration time caused false "crashed" reports for every live run.


def _is_owned_and_not_world_writable(path: Path) -> bool:
    """Return True only if path exists, is owned by current uid, and has no group/other write bits.
    Used for hardening status loads and untrusted checkpoint ingestion from target_dir.
    Any error (missing, permission, etc.) returns False (fail closed for security checks).
    """
    try:
        st = os.lstat(path)
        if (st.st_mode & 0o120000) == 0o120000:
            return False
        if st.st_uid != os.getuid():
            return False
        if st.st_mode & 0o022:
            return False
        return True
    except Exception:
        return False
