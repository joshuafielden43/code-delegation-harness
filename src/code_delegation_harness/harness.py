#!/usr/bin/env python3
"""
Grok Coding Delegate

A focused, production-oriented harness for delegating coding work to Grok
in a clean, structured way. Produces high-quality reviewable artifacts
(JSON + human report + ready-to-apply patch) even for long-running tasks.

Designed to keep the primary persona clean while getting real implementation
work done reliably.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def build_grok_prompt(task: str, target_dir: str, context: Optional[str] = None, constraints: Optional[str] = None) -> str:
    """Construct a strong, code-first prompt for Grok with structured final output."""
    prompt = f"""You are acting as a code-first implementation harness for a coding task.

TASK:
{task}

WORKING DIRECTORY (use this exactly):
{target_dir}

CRITICAL PATH RULES:
- The target directory above is the ONLY working directory. Use it as the base for ALL file operations.
- Always use full absolute paths when reading, writing, or referencing files (e.g. {target_dir}/path/to/file.py).
- Never assume relative paths or guess the location of the target files. The directory you were given is authoritative.
- If you need to inspect or modify a specific file mentioned in the task, construct its path by prefixing it with the WORKING DIRECTORY above.

INSTRUCTIONS:
- Work directly in the target directory using your available tools (read_file, search_replace, run_terminal_cmd, etc.).
- Focus on producing working code and making the requested changes.
- Be precise and minimal — only change what is necessary to complete the task.
- If you need to create new files or directories, do so.
- Do not add unnecessary personality or commentary. Treat this as a professional coding handoff.

**IMPORTANT - FINAL OUTPUT FORMAT:**
When you are completely finished, end your response with a clearly marked structured summary in this exact format:

=== DELEGATION SUMMARY ===
SUMMARY: <One paragraph plain-English summary of what was accomplished. Be precise about behavior changes.>

FILES_CREATED:
- path/to/new/file1.py
- path/to/new/file2.py

FILES_MODIFIED:
- path/to/changed/file.py (1-2 sentence description of what changed and why)

FILES_DELETED:
- path/to/deleted/file.py (if any)

VERIFICATION:
- <What was tested or checked>
- <Any commands run and their results>

NEXT_STEPS (if any):
- <Recommended follow-up actions>

CHANGE_SUMMARY:
- For each modified file, briefly note the net effect (e.g. "Added input validation and error handling", "Refactored X into Y for clarity").

NO_CHANGES:
- If you made no modifications at all (read-only inspection or analysis only), explicitly state: "No files were created, modified, or deleted."

OBSERVATIONS:
- For read-only or no-change runs: list the main files or areas you inspected and the key findings or recommendations in 1-3 short bullets. This turns inspection work into immediately usable signal.
- For runs that made changes: optional but welcome (e.g. "Noted two other call sites that may benefit from the same pattern later").

ERRORS (if any):
- List any errors, warnings, or partial failures encountered during the work.

=== END SUMMARY ===

Do not put the summary anywhere else. The wrapper will parse the section after the final "=== DELEGATION SUMMARY ===" marker.

Be explicit about whether changes were made. If nothing was changed, say so clearly in the NO_CHANGES section.
"""

    if context:
        prompt += f"\nADDITIONAL CONTEXT:\n{context}\n"

    if constraints:
        prompt += f"\nCONSTRAINTS / REQUIREMENTS:\n{constraints}\n"

    prompt += "\nBegin work now. Use tools to inspect the codebase first if needed, then implement."
    return prompt


def call_grok_headless(prompt: str, cwd: str, model: str = "grok-build", timeout: int = 1800, max_turns: int = 60) -> dict:
    """
    Call Grok in headless mode and return structured results.

    Supports long-running tasks by allowing configurable timeouts (default 30 minutes).
    When a task exceeds the timeout, the inner Grok may continue in background mode.
    """
    cmd = [
        "grok",
        "-p", prompt,
        "--cwd", cwd,
        "-m", model,
        "--always-approve",
        "--output-format", "json",
        "--max-turns", str(max_turns),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Try to parse JSON output
        try:
            data = json.loads(stdout)
            data["raw_stdout"] = stdout
            data["stderr"] = stderr
            data["exit_code"] = result.returncode
            return data
        except json.JSONDecodeError:
            return {
                "text": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "parse_error": True,
            }

    except subprocess.TimeoutExpired:
        return {
            "error": f"Grok call timed out after {timeout} seconds. The task may have continued in background mode.",
            "exit_code": -1,
            "timed_out": True,
            "timeout_seconds": timeout,
        }
    except Exception as e:
        return {"error": str(e), "exit_code": -1}


def _make_delegate_status(run_id: str, run_name: Optional[str], task: Optional[str],
                            target_dir: str, model: str, state: str = "waiting") -> dict:
    """Create a rich, queryable status record for background / long-running delegate runs."""
    task_snippet = ((task or "")[:140].replace("\n", " ").strip() + "...") if task else ""
    return {
        "run_id": run_id,
        "run_name": run_name,
        "task": task_snippet,
        "target_dir": target_dir,
        "model": model,
        "state": state,                 # waiting | completed | max_wait_exceeded
        "started_at": datetime.now().isoformat(),
        "elapsed_seconds": 0,
        "last_poll_at": None,
    }


def _write_status_file(status_file: Path, data: dict) -> None:
    """Atomic-ish write of delegate status with secure 600 file permissions."""
    try:
        status_file.write_text(json.dumps(data, indent=2))
        status_file.chmod(0o600)
    except Exception:
        pass


def _finalize_delegate_status(status_file: Optional[Path], clean_result: dict, run_name: Optional[str] = None) -> None:
    """Update (or create) a status file with final completion state after a run ends."""
    if not status_file:
        return
    try:
        existing = {}
        if status_file.exists():
            existing = json.loads(status_file.read_text())
        final_state = "completed" if clean_result.get("success") else "failed"
        if clean_result.get("status") == "no_changes":
            final_state = "completed_no_changes"
        elapsed = None
        if "started_at" in existing:
            try:
                started = datetime.fromisoformat(existing["started_at"])
                elapsed = int((datetime.now() - started).total_seconds())
            except Exception:
                pass

        final = {
            **existing,
            "state": final_state,
            "final_status": clean_result.get("status"),
            "ended_at": datetime.now().isoformat(),
            "elapsed_seconds": elapsed or existing.get("elapsed_seconds"),
            "run_name": run_name or existing.get("run_name"),
            "summary": clean_result.get("summary", "")[:200],
        }
        if clean_result.get("run_id"):
            final["run_id"] = clean_result["run_id"]
        _write_status_file(status_file, final)
    except Exception:
        pass


def prune_completed_status_files(target_dir: str, max_age_days: int = 7) -> None:
    """Remove old completed/failed status files older than max_age_days."""
    from datetime import datetime, timedelta

    target_path = Path(target_dir)
    now = datetime.now()
    limit = now - timedelta(days=max_age_days)

    for sf in target_path.glob(".cdh-run-*.status"):
        try:
            data = json.loads(sf.read_text())
            if data.get("state") in ("completed", "failed", "completed_no_changes", "max_wait_exceeded"):
                ended_at = data.get("ended_at")
                if ended_at:
                    ended_dt = datetime.fromisoformat(ended_at)
                    if ended_dt < limit:
                        sf.unlink()
                        print(f"[cdh] Pruned old status file: {sf.name}")
        except Exception:
            pass


def _wait_for_background_completion(
    prompt: str,
    cwd: str,
    model: str,
    max_wait: int,
    max_turns: int,
    poll_interval: int = 60,
    run_name: Optional[str] = None,
    task: Optional[str] = None,
    existing_status_file: Optional[Path] = None,
) -> dict:
    """
    After a timeout, keep polling until the background run completes or max_wait is exceeded.
    Reuses a pre-created launch status file when provided (consistent run_id + lifecycle across launch/wait/completion).
    Writes rich, persistent status files so the user (or --status / --resume) can see progress
    and history. Status files are left behind on completion for visibility.
    """
    start_time = time.time()

    if existing_status_file and existing_status_file.exists():
        try:
            existing = json.loads(existing_status_file.read_text())
            run_id = existing.get("run_id") or str(uuid.uuid4())[:8]
            status_file = existing_status_file
            status = existing
            status["state"] = "waiting"
            status["last_poll_at"] = datetime.now().isoformat()
            _write_status_file(status_file, status)
        except Exception:
            run_id = str(uuid.uuid4())[:8]
            status_file = Path(cwd) / f".cdh-run-{run_id}.status"
            status = _make_delegate_status(run_id, run_name, task, cwd, model, state="waiting")
            _write_status_file(status_file, status)
    else:
        run_id = str(uuid.uuid4())[:8]
        status_file = Path(cwd) / f".cdh-run-{run_id}.status"
        status = _make_delegate_status(run_id, run_name, task, cwd, model, state="waiting")
        _write_status_file(status_file, status)

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            status["state"] = "max_wait_exceeded"
            status["elapsed_seconds"] = int(elapsed)
            status["last_poll_at"] = datetime.now().isoformat()
            status["ended_at"] = datetime.now().isoformat()
            _write_status_file(status_file, status)
            return {
                "error": f"Waited {int(elapsed)}s for background completion but exceeded --max-wait of {max_wait}s.",
                "exit_code": -1,
                "timed_out": True,
                "waited_seconds": int(elapsed),
                "run_id": run_id,
                "run_name": run_name,
            }

        # Update and persist live status (visible to --status while waiting)
        status["elapsed_seconds"] = int(elapsed)
        status["last_poll_at"] = datetime.now().isoformat()
        _write_status_file(status_file, status)

        if not getattr(args, "quiet", False):
            print(f"[cdh] Still waiting for background run {run_id} ({run_name or ''})... ({int(elapsed)}s elapsed)")

        time.sleep(poll_interval)

        # Retry the call — if the background task finished, this should now return the final result
        result = call_grok_headless(
            prompt=prompt,
            cwd=cwd,
            model=model,
            timeout=300,
            max_turns=max_turns,
        )

        if not result.get("timed_out"):
            # Mark completed and leave the status file behind for history / --status
            exit_code = result.get("exit_code", 0)
            status["state"] = "completed"
            status["elapsed_seconds"] = int(elapsed)
            status["last_poll_at"] = datetime.now().isoformat()
            status["ended_at"] = datetime.now().isoformat()
            status["final_exit_code"] = exit_code
            status["final_status"] = "success" if exit_code in (0, None) else "failure_or_partial"
            _write_status_file(status_file, status)

            if not getattr(args, "quiet", False):
                print(f"[cdh] Background run {run_id} ({run_name or ''}) completed after {int(elapsed)}s total wait.")
            result["waited_for_background"] = True
            result["waited_seconds"] = int(elapsed)
            result["run_id"] = run_id
            result["run_name"] = run_name
            return result


def parse_delegation_summary(text: str) -> dict:
    """
    Extract the structured DELEGATION SUMMARY section if present.
    Now also captures CHANGE_SUMMARY and ERRORS sections when present.
    """
    marker = "=== DELEGATION SUMMARY ==="
    end_marker = "=== END SUMMARY ==="

    if marker not in text:
        return {"raw_text": text, "parsed": False}

    try:
        start = text.rfind(marker) + len(marker)
        end = text.find(end_marker, start)
        if end == -1:
            end = len(text)

        summary_block = text[start:end].strip()

        result = {
            "summary": "",
            "files_created": [],
            "files_modified": [],
            "files_deleted": [],
            "verification": "",
            "next_steps": "",
            "change_summary": "",
            "errors": [],
            "observations": "",
            "parsed": True
        }

        current_section = None
        for line in summary_block.splitlines():
            line = line.strip()
            if not line:
                continue

            upper = line.upper()
            if upper.startswith("SUMMARY:"):
                current_section = "summary"
                result["summary"] = line.split(":", 1)[1].strip()
            elif upper.startswith("FILES_CREATED:"):
                current_section = "files_created"
            elif upper.startswith("FILES_MODIFIED:"):
                current_section = "files_modified"
            elif upper.startswith("FILES_DELETED:"):
                current_section = "files_deleted"
            elif upper.startswith("VERIFICATION:"):
                current_section = "verification"
            elif upper.startswith("NEXT_STEPS"):
                current_section = "next_steps"
            elif upper.startswith("CHANGE_SUMMARY"):
                current_section = "change_summary"
            elif upper.startswith("ERRORS"):
                current_section = "errors"
            elif upper.startswith("OBSERVATIONS"):
                current_section = "observations"
            elif line.startswith("- "):
                if current_section in ("files_created", "files_modified", "files_deleted"):
                    result[current_section].append(line[2:].strip())
                elif current_section in ("verification", "next_steps", "summary", "change_summary", "observations"):
                    result[current_section] += ("\n" + line if result[current_section] else line)
                elif current_section == "errors":
                    result["errors"].append({"message": line[2:].strip()})
            else:
                if current_section in ("verification", "next_steps", "summary", "change_summary", "observations"):
                    result[current_section] += ("\n" + line if result[current_section] else line)
                elif current_section == "errors":
                    result["errors"].append({"message": line})

        return result

    except Exception as e:
        return {"raw_text": text, "parsed": False, "parse_error": str(e)}


def _determine_status(raw_result: dict, has_changes: bool) -> str:
    """Extracted status logic: maps raw result + change presence to one of the canonical statuses."""
    has_error = "error" in raw_result or raw_result.get("parse_error")
    exit_code = raw_result.get("exit_code", 0)

    if has_error or exit_code != 0:
        return "failure"
    elif not has_changes:
        return "no_changes"
    elif any(k in raw_result for k in ("stderr", "partial")):
        return "partial_success"
    else:
        return "success"


def _compute_diffs_and_stats(target_dir: str, modified: list) -> Tuple[dict, dict, dict, dict]:
    """Extracted diff logic: best-effort git diff + line stats + short human description + truncated preview per file."""
    if not target_dir or not modified:
        return {}, {}, {}, {}

    try:
        import subprocess
        import re
        diffs = {}
        stats = {}
        descriptions = {}
        previews = {}

        for entry in modified:
            if isinstance(entry, str):
                file_path = entry.split(" (")[0].strip()
                diff_result = subprocess.run(
                    ["git", "-C", target_dir, "diff", "HEAD", "--", file_path],
                    capture_output=True, text=True, timeout=8
                )
                if diff_result.returncode == 0 and diff_result.stdout.strip():
                    diff_text = diff_result.stdout.strip()
                    diffs[file_path] = diff_text

                    added = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
                    removed = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))
                    stats[file_path] = {"added_lines": added, "removed_lines": removed}

                    # Generate a short human-readable description (much richer heuristic)
                    desc_parts = []
                    if added > 0:
                        desc_parts.append(f"+{added}")
                    if removed > 0:
                        desc_parts.append(f"-{removed}")

                    # Richer signals
                    func_adds = len(re.findall(r'^\+def ', diff_text, re.MULTILINE))
                    func_mods = len(re.findall(r'^\+    def ', diff_text, re.MULTILINE)) + len(re.findall(r'^\+        def ', diff_text, re.MULTILINE))
                    class_adds = len(re.findall(r'^\+class ', diff_text, re.MULTILINE))
                    docstring_adds = len(re.findall(r'^\+    """', diff_text, re.MULTILINE)) + len(re.findall(r"^\+    '''", diff_text, re.MULTILINE))
                    type_hints = len(re.findall(r': [A-Za-z_][A-Za-z0-9_\[\], ]+ =', diff_text)) + len(re.findall(r' -> [A-Za-z_]', diff_text))
                    error_handling = len(re.findall(r'^\+.*(except|raise |try:)', diff_text, re.MULTILINE))
                    imports = len(re.findall(r'^\+(import |from .+ import)', diff_text, re.MULTILINE))

                    if func_adds:
                        desc_parts.append(f"{func_adds} function(s) added")
                    if func_mods and not func_adds:
                        desc_parts.append("function body updated")
                    if class_adds:
                        desc_parts.append(f"{class_adds} class(es) added")
                    if docstring_adds:
                        desc_parts.append("docstrings added")
                    if type_hints:
                        desc_parts.append("type hints")
                    if error_handling:
                        desc_parts.append("error handling improved")
                    if imports:
                        desc_parts.append("imports updated")

                    if not desc_parts:
                        desc = "Minor changes"
                    else:
                        desc = ", ".join(desc_parts)

                    descriptions[file_path] = desc

                    # Truncated preview: first ~12 lines of actual +/- content for immediate usability
                    preview_lines = []
                    for ln in diff_text.splitlines():
                        if ln.startswith(("@@", "diff --git", "index ", "---", "+++")):
                            continue
                        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")):
                            preview_lines.append(ln)
                        if len(preview_lines) >= 12:
                            break
                    if preview_lines:
                        previews[file_path] = "\n".join(preview_lines)

        return diffs, stats, descriptions, previews
    except Exception:
        return {}, {}, {}, {}


def normalize_result(raw_result: dict, target_dir: str = None) -> dict:
    """
    Take the raw Grok response and return a much cleaner, structured object.
    Adds:
    - Explicit no-op detection + "no_changes_made" flag
    - Richer per-file change summaries (stats + short human description) + optional diffs
    - Clear top-level status + categorized errors for partial failures

    Internal helpers extracted for modularity; public API and observable behavior unchanged.
    """
    text = raw_result.get("text", "") or raw_result.get("raw_stdout", "")
    parsed = parse_delegation_summary(text)

    created = parsed.get("files_created", []) or []
    modified = parsed.get("files_modified", []) or []
    deleted = parsed.get("files_deleted", []) or []

    has_changes = bool(created or modified or deleted)

    # Use extracted status helper
    status = _determine_status(raw_result, has_changes)

    clean = {
        "success": status in ("success", "partial_success", "no_changes"),
        "status": status,
        "summary": parsed.get("summary", "") if parsed.get("parsed") else (text[:600] + "..." if text else ""),
        "changes": {
            "created": created,
            "modified": modified,
            "deleted": deleted,
            "no_changes_made": not has_changes,
        },
        "change_summary": parsed.get("change_summary", ""),
        "verification": parsed.get("verification", ""),
        "next_steps": parsed.get("next_steps", ""),
        "observations": parsed.get("observations", "").strip() or None,
        "has_structured_summary": parsed.get("parsed", False),
        "metadata": raw_result.get("metadata", {}),
    }

    # Surface parsed errors if present
    if parsed.get("errors"):
        clean["errors"] = parsed["errors"]

    # Use extracted diff helper (now also returns richer per-file descriptions + usable previews)
    diffs, stats, descriptions, previews = _compute_diffs_and_stats(target_dir, modified)
    if diffs:
        clean["diffs"] = diffs
    if stats:
        clean["change_stats"] = stats
    if descriptions:
        clean["change_descriptions"] = descriptions
    if previews:
        clean["diff_previews"] = previews  # Truncated actual +/- lines for fast human scanning without external git

    # Error categorization
    errors = []
    if raw_result.get("error"):
        errors.append({"type": "wrapper_error", "message": raw_result["error"]})
    if raw_result.get("parse_error"):
        errors.append({"type": "parse_error", "message": "Failed to parse structured summary from Grok"})
    if not parsed.get("parsed", False):
        errors.append({
            "type": "missing_summary_marker",
            "message": "Grok completed work but omitted the structured === DELEGATION SUMMARY === block."
        })
    if raw_result.get("stderr"):
        errors.append({"type": "stderr", "message": raw_result["stderr"][:2000]})
    exit_code = raw_result.get("exit_code", 0)
    if exit_code not in (0, None):
        errors.append({"type": "nonzero_exit", "code": exit_code})

    if errors:
        clean["errors"] = errors
        if status == "success":
            clean["status"] = "partial_success"

    # Keep original for debugging
    clean["full_grok_response"] = text
    if raw_result.get("exit_code") is not None:
        clean["exit_code"] = raw_result["exit_code"]

    return clean


def render_human_report(result: dict) -> str:
    """
    Turn a normalized delegation result into a high-quality, scannable Markdown report
    optimized for quick human review of the END RESULT.

    This is the artifact Honey (or anyone) should review when a delegation completes.
    It surfaces the signal from the rich structured data without forcing them to read raw JSON.

    This function is intentionally defensive: it should never crash the wrapper.
    If something goes wrong while building sections, it will still return a usable
    (possibly partial) report plus an error note.
    """
    try:
        status = result.get("status", "unknown")
        status_emoji = {
            "success": "✅",
            "partial_success": "⚠️",
            "no_changes": "👁️",
            "failure": "❌",
        }.get(status, "❓")

        lines = []
        run_name = result.get("metadata", {}).get("run_name")
        title = f"# Delegation Report — {status_emoji} {status.upper()}"
        if run_name:
            title += f" ({run_name})"
        lines.append(title)
        lines.append("")

        # Quick stats for fast scanning of the end result
        changes = result.get("changes", {})
        created = len(changes.get("created", []) or [])
        modified = len(changes.get("modified", []) or [])
        deleted = len(changes.get("deleted", []) or [])
        has_patch = bool(result.get("patch_file"))

        stats_line = []
        if created:
            stats_line.append(f"{created} created")
        if modified:
            stats_line.append(f"{modified} modified")
        if deleted:
            stats_line.append(f"{deleted} deleted")
        if has_patch:
            stats_line.append("patch available")

        if stats_line:
            lines.append("**" + " • ".join(stats_line) + "**")
            lines.append("")

        # Prominent warning when the run timed out / went into background
        if result.get("timed_out"):
            lines.append("## ⚠️ Task Timed Out / Background Run")
            lines.append("The inner Grok run exceeded the configured timeout and may have continued in background mode.")
            lines.append("The artifacts below may be partial. Check the full JSON for any additional state or resumption info.")
            lines.append("")

        # Note when we successfully waited for a background run to finish
        if result.get("waited_for_background"):
            waited = result.get("waited_seconds", 0)
            run_name = result.get("run_name") or result.get("run_id")
            lines.append("## Background Completion")
            lines.append(f"This run originally timed out but the wrapper waited {waited}s for background completion.")
            if run_name:
                lines.append(f"Run: {run_name}")
            lines.append("Full artifacts below reflect the final result after the background task finished.")
            lines.append("")

        if result.get("resumed"):
            lines.append("## Resumed Background Run")
            lines.append("This delegation was resumed from a previous background wait using --resume.")
            lines.append("")

        # Quick Review Checklist (high-signal for end-result review)
        if created or modified or deleted:
            lines.append("## Quick Review Checklist")
            lines.append("- [ ] Read the Change Summary and Observations sections")
            if has_patch:
                lines.append("- [ ] Review the generated `.patch` file")
            lines.append("- [ ] Inspect the actual changed files in the working directory")
            lines.append("- [ ] Run relevant tests / verification steps")
            lines.append("- [ ] Decide: accept, request changes, or apply patch")
            lines.append("")

        # One-line summary
        summary = result.get("summary", "").strip()
        if summary:
            lines.append(f"**{summary}**")
            lines.append("")

        # Change summary (high signal)
        change_summary = result.get("change_summary", "").strip()
        if change_summary:
            lines.append("## Change Summary")
            lines.append(change_summary)
            lines.append("")

        # Changes section with rich details
        changes = result.get("changes", {})
        created = changes.get("created", []) or []
        modified = changes.get("modified", []) or []
        deleted = changes.get("deleted", []) or []
        no_changes = changes.get("no_changes_made", False)

        if no_changes:
            lines.append("## No Code Changes")
            obs = result.get("observations")
            if obs:
                lines.append("Grok performed read-only inspection / analysis. Key findings below.")
            else:
                lines.append("No files were created, modified, or deleted.")
            lines.append("")
        else:
            if created:
                lines.append("## Files Created")
                for f in created:
                    lines.append(f"- `{f}`")
                lines.append("")

            if modified:
                lines.append("## Files Modified")
                stats = result.get("change_stats", {})
                descs = result.get("change_descriptions", {})
                previews = result.get("diff_previews", {})

                for f in modified:
                    line = f"- `{f}`"
                    if f in descs:
                        line += f" — {descs[f]}"
                    lines.append(line)

                    # Stats
                    if f in stats:
                        s = stats[f]
                        lines.append(f"  - Lines: +{s.get('added_lines', 0)} / -{s.get('removed_lines', 0)}")

                    # Preview (the actual useful diff bits)
                    if f in previews:
                        lines.append("  ```diff")
                        for pl in previews[f].splitlines()[:12]:
                            lines.append(f"  {pl}")
                        lines.append("  ```")
                lines.append("")

            if deleted:
                lines.append("## Files Deleted")
                for f in deleted:
                    lines.append(f"- `{f}`")
                lines.append("")

            # Prominently surface the patch file for easy review + collaboration
            patch_file = result.get("patch_file")
            if patch_file:
                lines.append("## Patch File (Ready to Review / Apply)")
                lines.append(f"A complete unified diff is available at:")
                lines.append(f"")
                lines.append(f"    {patch_file}")
                lines.append(f"")
                lines.append("You can apply it with:")
                lines.append("    git apply " + Path(patch_file).name)
                lines.append("or review it directly in your editor / diff tool.")
                lines.append("")

            # Concrete, actionable guidance for reviewing the delivered end result
            if created or modified or deleted:
                lines.append("## How to Review This Change")
                lines.append("1. Read the Change Summary and per-file details above.")
                if patch_file:
                    lines.append("2. Open and review the generated `.patch` file.")
                lines.append("3. Look at the actual files in the working directory.")
                lines.append("4. Follow the Verification steps listed later in this report.")
                lines.append("5. Accept, request changes, or apply the patch as appropriate.")
                lines.append("")

        # Observations (critical for review of inspection work and for end-result context)
        observations = result.get("observations")
        if observations:
            lines.append("## Observations / Key Findings")
            lines.append(observations)
            lines.append("")

        # Errors / partial issues (actionable for the reviewer)
        errors = result.get("errors", []) or []
        if errors:
            lines.append("## Issues Encountered")
            for err in errors:
                etype = err.get("type", "error")
                msg = err.get("message", str(err))
                lines.append(f"- **{etype}**: {msg}")
            lines.append("")
            lines.append("> Review the full output and verification steps carefully before accepting the changes.")
            lines.append("")

        # Verification + next steps
        verification = result.get("verification", "").strip()
        if verification:
            lines.append("## Verification Performed")
            lines.append(verification)
            lines.append("")

        next_steps = result.get("next_steps", "").strip()
        if next_steps:
            lines.append("## Recommended Next Steps")
            lines.append(next_steps)
            lines.append("")

        # Footer metadata (useful when reviewing end results later)
        meta = result.get("metadata", {})
        lines.append("---")
        lines.append(f"**Task**: {meta.get('task', 'n/a')}")
        if meta.get("run_name"):
            lines.append(f"**Run Name**: {meta.get('run_name')}")
        lines.append(f"**Target**: {meta.get('target_directory', 'n/a')}")
        lines.append(f"**Timestamp**: {meta.get('timestamp', 'n/a')}")
        lines.append(f"**Model**: {meta.get('model', 'n/a')}")
        lines.append("")
        lines.append("*Generated by code-delegation-harness — review the actual code changes in the working directory for the definitive end result.*")

        return "\n".join(lines)

    except Exception as e:
        # Defensive fallback — never let report generation take down the whole run
        error_note = f"\n\n---\n**Report Generation Error**: {str(e)}\nPartial or no human-readable report could be produced. Use the JSON output instead."
        return f"# Delegation Report — ❓ ERROR\n\nReport generation failed.\n{error_note}"


def _print_dry_run_preview(args, target_dir: str) -> None:
    """Emit clean, review-friendly dry-run output. Never launches Grok or writes any files."""
    quiet = getattr(args, "quiet", False)

    if not quiet:
        print("[cdh] DRY RUN — no inner delegation will be launched, no files will be written")
        print()

    if not quiet:
        print("=== Effective Configuration ===")
        print(f"task: {args.task}")
        print(f"target_directory: {target_dir}")
        print(f"model: {args.model}")
        print(f"timeout: {args.timeout}s")
        print(f"max_turns: {args.max_turns}")
        print(f"wait_for_completion: {getattr(args, 'wait_for_completion', False)}")
        print(f"max_wait: {getattr(args, 'max_wait', 0)}s (applies only with --wait-for-completion)")
        print(f"poll_interval: {getattr(args, 'poll_interval', 60)}s")
        print(f"run_name: {args.run_name or '(none)'}")
        print(f"context: {'provided' if args.context else '(none)'}")
        print(f"constraints: {'provided' if args.constraints else '(none)'}")
        print(f"output_file: {args.output_file or '(stdout)'}")
        print()

    if not quiet:
        prompt = build_grok_prompt(
            task=args.task,
            target_dir=target_dir,
            context=args.context,
            constraints=args.constraints,
        )
        print("=== Full Prompt (exact text that would be sent to inner Grok) ===")
        print(prompt)
        print()

    if not quiet:
        print("=== Expected Output Structure ===")
        if args.output_file:
            out = Path(args.output_file)
            stem = out.stem
            parent = out.parent
            print(f"Primary JSON:     {out}")
            print(f"Human report:     {parent / (stem + '.report.md')}")
            print(f"Run metadata:     {parent / (stem + '.run-meta.json')}")
            print("Patch file:       <same-stem>.patch   (created only if task produces code changes)")
            print()
            print(f"Status file:      {target_dir}/.cdh-run-<8-char-id>.status")
        else:
            print("- JSON result printed to stdout")
            print(f"- Status file (always): {target_dir}/.cdh-run-<8-char-id>.status")
            print("- (Add --output-file to also receive .report.md, .run-meta.json, and .patch when applicable)")
        print()
        print("To execute for real, re-run the identical command WITHOUT --dry-run.")
        print("(Tip: --output-file is strongly recommended for any non-trivial task to get the full reviewable artifacts.)")
        print()
    else:
        # True minimal output in quiet mode
        if args.output_file:
            out = Path(args.output_file)
            print(str(out))
            print(str(out.parent / (out.stem + ".report.md")))
            if True:  # we always expect these in the expected structure
                print(str(out.parent / (out.stem + ".run-meta.json")))
            print(f"{target_dir}/.cdh-run-<id>.status")
        else:
            print("Dry run complete (quiet). No files written.")


def main():
    # Resolve version dynamically from package metadata (set by pyproject.toml).
    # Works for pip installs, editable installs, and direct dev execution via shims.
    try:
        import importlib.metadata
        _VERSION = importlib.metadata.version("code-delegation-harness")
    except Exception:
        _VERSION = "0.2.1"

    parser = argparse.ArgumentParser(description="Delegate coding work to Grok")
    parser.add_argument("--task", help="The coding task to perform")
    parser.add_argument("--target-dir", help="Working directory for the task")
    parser.add_argument("--context", help="Additional context for the task")
    parser.add_argument("--constraints", help="Hard constraints or requirements")
    parser.add_argument("--model", default="grok-build", help="Model to use")
    parser.add_argument("--output-file", help="Optional path to write structured results")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout in seconds for the inner model run (default: 1800 = 30 minutes)")
    parser.add_argument("--max-turns", type=int, default=60, help="Maximum turns for the inner model run (default: 60)")
    parser.add_argument("--wait-for-completion", action="store_true", help="If the inner run times out, keep polling/waiting for background completion instead of failing immediately")
    parser.add_argument("--max-wait", type=int, default=7200, help="Maximum total seconds to wait for a background run to complete (default: 7200 = 2 hours)")
    parser.add_argument("--poll-interval", type=int, default=60, help="Seconds between polls when waiting for background completion (default: 60)")
    parser.add_argument("--status", action="store_true", help="Show status of active + completed background/long-running delegate runs in the target directory (persistent .status files) and exit")
    parser.add_argument("--run-name", help="Optional human-friendly name for this run (used in status files and reports for long-running tasks)")
    parser.add_argument("--resume", help="Resume waiting for a previous background run using its run_id or path to a .status file")
    parser.add_argument("--dry-run", action="store_true", help="Preview the full prompt, effective flags, target directory, and expected output artifacts without launching the inner agent or writing any status/output files")
    parser.add_argument("--prune", type=int, nargs="?", const=7, help="Prune completed/failed status files older than N days (default: 7)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output. Only show errors and final artifact locations.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show more detailed internal progress messages.")
    parser.add_argument("--version", action="version", version=f"code-delegation-harness {_VERSION}")

    args = parser.parse_args()

    # Set verbosity level: 0 = quiet, 1 = normal, 2 = verbose
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1

    def _vprint(level: int, msg: str):
        """Print only if current verbosity >= level"""
        if verbosity >= level:
            print(msg)

    # Make verbosity available to the rest of main
    globals()["_verbosity"] = verbosity
    globals()["_vprint"] = _vprint

    # Operational / standalone commands that do not require --task / --target-dir
    is_standalone = bool(
        args.status or
        args.resume or
        (args.prune is not None) or
        args.dry_run
    )

    if not is_standalone:
        if not args.task:
            parser.error("--task is required")
        if not args.target_dir:
            parser.error("--target-dir is required")

    # Guard against None for any code paths that still assume these are set
    if not is_standalone and (not args.task or not args.target_dir):
        sys.exit(1)

    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.exists():
            # treat as run_id
            candidates = list(Path(".").glob(f"**/.cdh-run-{args.resume}*.status"))
            if not candidates:
                candidates = list(Path(".").glob(f"**/*{args.resume}*.status"))
            if candidates:
                resume_path = candidates[0]
            else:
                print(f"Could not find status file for run '{args.resume}'")
                sys.exit(1)

        try:
            data = json.loads(resume_path.read_text())
            run_id = data.get("run_id")
            state = data.get("state", "unknown")
            original_target = data.get("target_dir") or "."
            original_prompt = data.get("original_prompt") or data.get("task", "")
            original_model = data.get("model", args.model)
            run_name = data.get("run_name")

            if state in ("completed", "max_wait_exceeded"):
                # Smart short-circuit: the run already finished. No need to re-wait.
                elapsed = data.get("elapsed_seconds", "?")
                ended = data.get("ended_at", "")
                final_exit = data.get("final_exit_code")
                final_status = data.get("final_status", state)
                task_preview = (data.get("task") or "")[:80].replace("\n", " ")

                print(f"[cdh] Run {run_id} ({run_name or 'unnamed'}) already finished (state: {state}).")
                print(f"  Elapsed: {elapsed}s | Ended: {ended or 'n/a'} | Final exit: {final_exit} | Status: {final_status}")
                if task_preview:
                    print(f"  Task: {task_preview}...")
                print()
                print("Look for companion artifacts in the target directory or the original --output-file location:")
                print("  - <output>.json + <output>.report.md + <output>.patch (if changes were made)")
                print("  - <output>.run-meta.json")
                print(f"  - Or run:  ls -l {original_target}/.cdh-run-{run_id}*")
                sys.exit(0 if final_exit in (0, None) else 1)

            print(f"[cdh] Resuming background run {run_id} in {original_target}...")

            resume_status_file = resume_path if resume_path.suffix == ".status" else None

            # Enter waiting mode using the saved parameters
            result = _wait_for_background_completion(
                prompt=original_prompt,
                cwd=original_target,
                model=original_model,
                max_wait=args.max_wait,
                max_turns=args.max_turns,
                poll_interval=args.poll_interval,
                run_name=run_name,
                task=data.get("task") or original_prompt,
                existing_status_file=resume_status_file,
            )

            # Proceed with normal result processing below
            # (We override args for downstream consistency)
            args.target_dir = original_target
            target_dir = os.path.abspath(original_target)

        except Exception as e:
            print(f"Failed to resume run: {e}")
            sys.exit(1)

    if args.status:
        target_dir = os.path.abspath(args.target_dir) if args.target_dir else "." if args.target_dir else "."
        status_files = sorted(Path(target_dir).glob(".cdh-run-*.status"))
        if not status_files:
            print("No delegate background runs found in", target_dir)
            sys.exit(0)

        active = []
        completed = []
        for sf in status_files:
            try:
                data = json.loads(sf.read_text())
                entry = {
                    "file": sf.name,
                    "state": data.get("state", "unknown"),
                    "name": data.get("run_name") or data.get("run_id"),
                    "elapsed": data.get("elapsed_seconds", "?"),
                    "task": (data.get("task") or "")[:70].replace("\n", " "),
                    "started": data.get("started_at", "")[:19],
                    "ended": data.get("ended_at", ""),
                    "final_status": data.get("final_status") or data.get("state"),
                }
                if entry["state"] in ("waiting", "launched", "running"):
                    active.append(entry)
                else:
                    completed.append(entry)
            except Exception:
                completed.append({"file": sf.name, "state": "unreadable", "name": "?", "elapsed": "?", "task": ""})

        if active:
            print(f"Active / in-progress delegate runs in {target_dir}:")
            for e in active:
                state_label = e.get("state", "active")
                print(f"  {e['file']} | {state_label} | {e['name']} | {e['elapsed']}s | started {e['started']} | {e['task']}...")
            print()

        if completed:
            print(f"Completed / historical delegate runs in {target_dir}:")
            for e in completed:
                state_label = e.get("state", "done")
                print(f"  {e['file']} | {state_label} | {e['name']} | {e['elapsed']}s | {e['task']}")
            print()

        print("Use --resume <run_id or .status filename> to re-attach waiting, or inspect the companion .run-meta.json / .report.md for finished runs that used --output-file.")
        sys.exit(0)

    if args.prune is not None:
        target_dir = os.path.abspath(args.target_dir) if args.target_dir else "." if args.target_dir else "."
        prune_completed_status_files(target_dir, max_age_days=args.prune)
        sys.exit(0)

<<<<<<< Updated upstream
    if not args.target_dir:
        print("Error: --target-dir is required (unless using --status)")
        sys.exit(1)

    target_dir = os.path.abspath(args.target_dir)
=======
    target_dir = os.path.abspath(args.target_dir) if args.target_dir else "."
>>>>>>> Stashed changes
    if not os.path.isdir(target_dir):
        print(f"Error: Target directory does not exist: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # Gentle warning for non-git directories (rich diffs, previews, and patch generation depend on git)
    if not os.path.isdir(os.path.join(target_dir, ".git")) and not getattr(args, "quiet", False):
        print("[cdh] Warning: Target directory is not a Git repository. "
              "Rich diff reports, previews, and .patch file generation will be skipped.", file=sys.stderr)

    if args.dry_run:
        _print_dry_run_preview(args, target_dir)
        sys.exit(0)

    # Always create a launch status file for full observability and production reliability.
    # This makes --status useful for every delegation and enables clean resumption patterns.
    launch_run_id = str(uuid.uuid4())[:8]
    launch_status_file = Path(target_dir) / f".cdh-run-{launch_run_id}.status"
    launch_status = _make_delegate_status(
        launch_run_id, args.run_name, args.task, target_dir, args.model, state="launched"
    )
    launch_status["status_file_path"] = str(launch_status_file)
    _write_status_file(launch_status_file, launch_status)

    if not getattr(args, "quiet", False):
        print(f"[cdh] Status: {launch_status_file.name} (launched)")

    prompt = build_grok_prompt(
        task=args.task,
        target_dir=target_dir,
        context=args.context,
        constraints=args.constraints,
    )

    if not getattr(args, "quiet", False):
        print(f"[cdh] Starting delegation at {datetime.now().isoformat()}")
        print(f"[cdh] Task: {args.task[:100]}...")
        print(f"[cdh] Working in: {target_dir}")
    # In quiet mode we intentionally print almost nothing here — only errors and final artifacts

    result = call_grok_headless(prompt, cwd=target_dir, model=args.model, timeout=args.timeout, max_turns=args.max_turns)

    # Handle background / long-running case
    if result.get("timed_out") and args.wait_for_completion:
        run_name = args.run_name or None
        if not getattr(args, "quiet", False):
            print(f"[cdh] Inner run timed out after {args.timeout}s. Entering wait-for-completion mode (max wait: {args.max_wait}s, poll every {args.poll_interval}s)...")
        result = _wait_for_background_completion(
            prompt=prompt,
            cwd=target_dir,
            model=args.model,
            max_wait=args.max_wait,
            max_turns=args.max_turns,
            poll_interval=args.poll_interval,
            run_name=run_name,
            task=args.task,
            existing_status_file=launch_status_file,
        )

    # Add metadata
    result["metadata"] = {
        "task": args.task,
        "target_directory": target_dir,
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "run_name": args.run_name,
    }

    # Propagate background/resume identifiers for consistent artifacts + reports
    for key in ("run_id", "run_name", "waited_for_background", "waited_seconds", "resumed"):
        if key in result and key not in result["metadata"]:
            result["metadata"][key] = result[key]

    # Produce clean structured output (the main improvement)
    clean_result = normalize_result(result, target_dir=target_dir)

    # Surface timeout / background run information clearly on the *clean* result so reports + JSON + run-meta see them
    if result.get("timed_out"):
        clean_result["timed_out"] = True
        clean_result["timeout_seconds"] = result.get("timeout_seconds")
        if "errors" not in clean_result:
            clean_result["errors"] = []
        clean_result["errors"].append({
            "type": "timeout",
            "message": result.get("error", "Task exceeded timeout and may have continued in background mode.")
        })

    # Propagate background completion / resume flags to clean result for consistent artifacts
    for k in ("waited_for_background", "waited_seconds", "run_id", "run_name", "resumed"):
        if k in result and k not in clean_result:
            clean_result[k] = result[k]

    # If we created a launch status file, make sure the run_id is known
    if launch_run_id and "run_id" not in clean_result:
        clean_result["run_id"] = launch_run_id

    output = json.dumps(clean_result, indent=2)

    if args.output_file:
        out_path = Path(args.output_file)

        # Generate patch (if any) *before* writing files so patch_file is in the JSON + report
        modified = clean_result.get("changes", {}).get("modified", []) or []
        git_target = clean_result.get("metadata", {}).get("target_directory") or target_dir
        if modified and git_target:
            patch_path = out_path.with_suffix(".patch")
            try:
                patch_parts = []
                for entry in modified:
                    file_path = entry.split(" (")[0].strip() if isinstance(entry, str) else entry
                    diff_result = subprocess.run(
                        ["git", "-C", git_target, "diff", "HEAD", "--", file_path],
                        capture_output=True, text=True, timeout=10
                    )
                    if diff_result.returncode == 0 and diff_result.stdout.strip():
                        patch_parts.append(diff_result.stdout.strip())

                if patch_parts:
                    full_patch = "\n".join(patch_parts)
                    patch_path.write_text(full_patch + "\n")
                    print(f"[cdh] Ready-to-apply patch written to {patch_path}")
                    clean_result["patch_file"] = str(patch_path)
                    # Re-serialize so the JSON also contains the patch_file reference
                    output = json.dumps(clean_result, indent=2)
            except Exception as e:
                print(f"[cdh] Warning: Could not generate patch: {e}")

        out_path.write_text(output)
        print(f"[cdh] Structured results written to {out_path}")

        # Write a run metadata file for reproducibility (especially useful for long/background runs)
        meta = {
            "task": args.task,
            "target_directory": target_dir,
            "model": args.model,
            "run_name": args.run_name,
            "run_id": clean_result.get("run_id") or result.get("run_id"),
            "timeout": args.timeout,
            "max_turns": args.max_turns,
            "wait_for_completion": args.wait_for_completion,
            "max_wait": args.max_wait,
            "poll_interval": args.poll_interval,
            "timestamp": datetime.now().isoformat(),
        }
        if clean_result.get("waited_for_background"):
            meta["waited_seconds"] = clean_result.get("waited_seconds")
        (out_path.parent / f"{out_path.stem}.run-meta.json").write_text(json.dumps(meta, indent=2))

        # Always emit the high-quality human review report next to the JSON.
        # This is the END RESULT artifact intended for quick human review.
        report_path = out_path.with_suffix(".report.md")
        report = render_human_report(clean_result)
        report_path.write_text(report)
        print(f"[cdh] Human review report written to {report_path}")

        # Surface the complete, ready-to-use end result artifacts
        if getattr(args, "quiet", False):
            print(str(out_path))
            if clean_result.get("patch_file"):
                print(str(clean_result['patch_file']))
        else:
            print("\n[cdh] Artifacts ready:")
            print(f"  {out_path}")
            print(f"  {report_path}")
            if clean_result.get("patch_file"):
                print(f"  {clean_result['patch_file']}")
            meta_path = out_path.parent / f"{out_path.stem}.run-meta.json"
            if meta_path.exists():
                print(f"  {meta_path}")
            print(f"  {target_dir}/.cdh-run-{clean_result.get('run_id', launch_run_id)}.status")

        _finalize_delegate_status(launch_status_file, clean_result, args.run_name)
    else:
        if not getattr(args, "quiet", False):
            print(output)
        _finalize_delegate_status(launch_status_file, clean_result, args.run_name)

    # Return non-zero if Grok had issues
    if clean_result.get("exit_code", 0) != 0 or not clean_result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()