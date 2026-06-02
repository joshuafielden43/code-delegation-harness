# Usage Notes

## Professional CLI Usage

The recommended way to use the tool is via the `gcdh` command.

See [Installation](installation.md) for how to get the command.

### How It Works

1. Invoke `gcdh` with a clear task, target directory, and optional context/constraints.
2. The harness builds a strong, constrained prompt and runs Grok in the target directory.
3. On completion it produces the full set of high-quality review artifacts:
   - Structured JSON
   - Human-optimized `.report.md` (with checklists)
   - Ready-to-apply `.patch` (when changes were made)
   - `.run-meta.json` for reproducibility
4. Long-running / background tasks are handled gracefully with persistent status files, `--status`, `--resume`, and `--wait-for-completion`.

### Best Practices

- Always use `--output-file` for any non-trivial task.
- Use `--quiet` (`-q`) for clean automation and agent-driven runs.
- Use `--dry-run` (ideally with `--quiet`) before committing to long or expensive work.
- **For any serious, ambitious, or long-running dogfood work** (full skill extensions, production-grade features, Proxmox-style appliance work, anything that needs to run for hours and actually finish): **use --long-running (or --keep-driving)**.

  This is the single most important flag for real work. It:
  - Bumps timeouts, turns, and waits to realistic multi-hour values.
  - Injects the ruthless "job to the end" + mandatory fresh verification / anti-stale-data language.
  - Enables dynamic fresh checkpoint injection on every background probe.

  Example for real dogfood:
  ```bash
  gcdh --long-running --wait-for-completion --max-wait 14400 \
       --task "Extend the existing proxmox-control skill with guest-exec + supporting fixes..." \
       --target-dir ~/.hermes/skills/proxmox-control \
       --output-file /tmp/proxmox-run.json
  ```

  You should use this for most real harness dogfood runs. Not every tiny one-off task needs it, but anything that matters does.

## Notes

The harness prioritizes reliable end-result artifacts over incremental chat. Use `--output-file` for the best experience on any non-trivial task.

## Notes for Honey

When delegating, be as specific as possible in the task description. The better the spec, the better the results.

### End-Result Review Reports + Patch Files
When you use `--output-file` (recommended), the wrapper now automatically emits three artifacts for the END RESULT:

1. `foo.json` — the full structured machine-readable result
2. `foo.report.md` — the primary human review document (status, rich change details with previews, observations, issues, verification, etc.)
3. `foo.patch` (when modifications were made) — a ready-to-apply unified diff. This is the collaboration artifact: review the .report.md, then inspect/apply the .patch directly.

Example usage that produces all three:
```bash
bin/gcdh \
  --task "..." \
  --target-dir /path/to/project \
  --output-file /tmp/delegation-result.json
```

You then open `/tmp/delegation-result.report.md` first for the high-signal review, and use the `.patch` for actual application or deeper diff review.

### Long-Running Tasks & Background Runs

**For any real dogfood or ambitious implementation work, start with this pattern:**

```bash
bin/gcdh \
  --long-running \
  --wait-for-completion \
  --max-wait 14400 \
  --task "..." \
  --target-dir /path/to/project \
  --output-file /tmp/delegation-result.json \
  --run-name "my-important-work" \
  --quiet
```

`--long-running` is strongly recommended for almost all serious runs. It is the primary "make this job actually finish" switch.

For big tasks that may exceed the inner agent's default timeout, use:

```bash
bin/gcdh \
  --task "..." \
  --target-dir /path/to/project \
  --output-file /tmp/delegation-result.json \
  --timeout 3600 \
  --max-turns 120 \
  --wait-for-completion \
  --max-wait 14400 \
  --poll-interval 120 \
  --run-name "my-big-refactor"
```

**For ambitious multi-hour implementation (e.g. full Proxmox skill extensions with guest-exec, resize, discovery fixes, tests, promotion — the primary dogfood target):**

### The Full "Worth Checking In" Recipe for Serious Work (especially from inside constrained environments like this TUI)

When you are inside a short-timeout wrapper (the Grok Build TUI, grok CLI sessions, CI with hard kill timers, etc.) and you need a real LLM to do hours of ambitious implementation without the job dying and leaving partial broken state in the live target:

1. **Always** use `--long-running` (or `--keep-driving`).
2. Pair it with `--wait-for-completion --max-wait 86400 --output-file ... --run-name "something-good"`.
3. When launched from a hostile short wrapper, the harness now **auto-detects** and **auto-escapes** the entire invocation into a detached tmux session (sets `GCDH_IN_TMUX` guard). The short-lived parent process exits cleanly so the outer 300s SIG15 cannot kill the real work. You (or the agent) attach later with `tmux attach -t <session>` or just let it cook and use `--status` / `--resume`.
4. The harness also **auto-reaps** any dead prior runs (using heartbeat + PID probe) at the start of every new `--long-running` launch. Combined with the strict safe live-target mutation rule, this means previous crashes cannot leave the real skill/infra in a half-edited untestable state.
5. The prompt now forces (as non-negotiable first action): create an isolated working copy of the live target inside the harness `--target-dir`. All edits happen there. Only a complete, tested, reviewable promotion ever touches the real location.

Example that triggers the full power (auto-escape + auto-reap + safe workspace + ruthless drive):

```bash
gcdh --long-running \
  --wait-for-completion \
  --max-wait 86400 \
  --output-file /tmp/proxmox-appliance-$(date +%s).json \
  --run-name "proxmox-guest-exec-resize-full" \
  --quiet \
  --task "..." \
  --target-dir /tmp/real-work-for-this-run \
  --context "..." 
```

If you are already inside the TUI when you run the above, the harness will print that it is auto-escaping into tmux and do it. The job survives even if this TUI session is killed.

This combination is what makes the harness capable of letting a strong LLM finish substantial work without constant outer babysitting or manual repair passes on the target.

Use this pattern for anything that matters. The harness is now built to make check-in / check-out sessions on real ambitious work actually worth it.

```bash
bin/gcdh \
  --task "..." \
  --target-dir /path/to/skill \
  --output-file /tmp/proxmox-appliance-run.json \
  --long-running \
  --wait-for-completion \
  --max-wait 86400 \
  --run-name "proxmox-guest-exec-v1" \
  --quiet
```

- `--long-running` (alias `--keep-driving`) is the new explicit "this is a serious long job that must finish" mode. It auto-bumps timeouts/turns/waits (4h/300/24h defaults if not already higher), enables an immediate first probe on wait entry + maximum dynamic PROGRESS.json injection on every background probe, and (when True) triggers an extra emphasis paragraph. The core ruthless anti-stale + job-to-the-end + "mandatory fresh live verification" language is now present on *every* invocation (unconditional in the built-in prompt); the flag signals long-running intent and adds the extra paragraph + operational bumps for ambitious Proxmox-style dogfood.
- This combination (plus the agent's own frequent PROGRESS.json + the harness's anti-stale + checkpoint recovery) is what makes real end-to-end dogfood on live hardware succeed without babysitting.
- Always pair with `--output-file` for the full reviewable artifact set (.json + .report.md + .patch + .run-meta.json).
- Use `--status` and `--resume <run-id>` liberally across host restarts or long pauses.
- The built-in prompt + dynamic injection now make "stale data" (e.g. old VM references) extremely unlikely; every invocation forces fresh verification as step 0.

- `--wait-for-completion` makes the wrapper automatically poll until the background run finishes (instead of failing on the first timeout).
- Use `--run-name` to give long runs a friendly label (appears in status files, --status output, and reports).
- Use `--status --target-dir .` later to see *both active waiting runs and recently completed ones* (status files are now left behind on completion for history and correlation with artifacts).
- Use `--resume <run-id-or-status-file>` (or just the friendly --run-name value if unambiguous) to re-attach to a previous background wait.
- The .report.md and run-meta.json will clearly document background timing, waited_seconds, and resumption.
- Named persistent status files (`.grok-delegate-run-<id>.status`) are now written at launch for any run using `--run-name` or `--wait-for-completion` (state starts as "launched", transitions to "waiting" if background polling begins, then "completed" / "failed" at the end). They contain task snippet, timing, full state machine, and final outcome. `--status` shows launched + active + historical runs. These files are the primary way to observe and resume long-running delegate activity.
- For pure "fire and forget" without --wait, the first invocation will surface the timeout; subsequent --status / --resume in the same tree lets you observe or attach later if desired.

### Dry-Run Preview (`--dry-run`)
Before launching a large or long-running task, use `--dry-run` to inspect exactly what would happen:

```bash
bin/gcdh \
  --task "..." \
  --target-dir /path/to/project \
  --output-file /tmp/preview.json \
  --constraints "..." \
  --dry-run
```

The output includes:
- Full effective configuration (all flags, resolved absolute target directory, presence of context/constraints)
- The complete prompt that will be sent to the inner Grok (including the critical path rules and the required `=== DELEGATION SUMMARY ===` contract)
- A clear preview of every artifact that would be created on a real run (`.json`, `.report.md`, `.run-meta.json`, optional `.patch`, and the persistent status file)

Nothing is executed and no files (including status files) are written. This is the recommended first step for any high-stakes or multi-hour delegation.

## Expected Output Format (Improved late May 2026)

The wrapper now returns significantly richer and more reliable structured output:

```json
{
  "success": true,
  "status": "success" | "partial_success" | "no_changes" | "failure",
  "summary": "...",
  "changes": {
    "created": [...],
    "modified": [...],
    "deleted": [...],
    "no_changes_made": false
  },
  "change_summary": "Added input validation to login endpoint...",
  "change_stats": {
    "src/auth.py": { "added_lines": 12, "removed_lines": 3 }
  },
  "change_descriptions": {
    "src/auth.py": "+12, -3, 1 function added, error handling improved, docstrings added"
  },
  "diff_previews": {
    "src/auth.py": "+    if not token or not token.strip():\n+        raise ValueError(\"...\")\n+    ... (truncated to first ~12 changed lines)"
  },
  "diffs": {
    "src/auth.py": "diff --git ..."
  },
  "observations": "Reviewed the full auth flow. Noted that refresh tokens are stored in localStorage (consider httpOnly cookie).",
  "verification": "...",
  "next_steps": "...",
  "errors": [ ... ]   // present on partial_success or failure
}
```

Key improvements:
- Explicit `status` + `no_changes_made` for read-only / no-op tasks
- `change_stats` with line counts per file
- `change_descriptions`: short human-readable summary per modified file (e.g. "+14, -3, 2 functions added, error handling improved, docstrings added")
- `diff_previews`: truncated actual +/- lines (first ~12) so output is self-contained for quick review
- `observations`: key findings from read-only / inspection runs (turns no-op into useful signal)
- Optional `diffs` (best-effort via git)
- Better error categorization

The parser looks for the `=== DELEGATION SUMMARY ===` block. Grok is now explicitly instructed to call out no-changes cases and surface errors clearly.

**Note on long-running runs (0.3.0+):** If the inner agent omits the exact markers (common after very long or interrupted runs), the harness performs best-effort recovery using the agent's own `PROGRESS.json` checkpoints. The result will include `summary_synthesized_from_checkpoint: true` and the human report will contain a clear `♻️ Summary Synthesized from Agent Checkpoints` section with review guidance. This is a supported recovery path.

Example of the human review report (what you actually read for the end result):

```markdown
# Delegation Report — ✅ SUCCESS

**Added Google-style docstrings and type hints to format_currency...**

## Change Summary
Added type hints and full Google-style docstring; no logic changes

## Files Modified
- `utils/helpers.py` — +12, -0, docstrings added, type hints

  - Lines: +12 / -0

  ```diff
  +def format_currency(amount: float, currency: str = "USD") -> str:
  +    """
  +    Format a monetary amount...
  +    """
  ```

## Verification Performed
Function tested before/after with sample inputs; behavior identical

## Recommended Next Steps
Run the full test suite

---
**Task**: ...
**Target**: ...
*Generated by grok-coding-delegate — review the actual code changes in the working directory for the definitive end result.*
```


## Internal Structure (refactored late May 2026)

The core output normalization logic lives in `normalize_result` (src/grok_delegate/harness.py). For clarity and future evolution the following were extracted into private helpers while preserving the exact public API and behavior:

- `_determine_status(raw_result, has_changes)` — centralizes the success / partial_success / no_changes / failure rules.
- `_compute_diffs_and_stats(target_dir, modified)` — encapsulates git diff + line stats + rich descriptions + truncated previews (returns 4-tuple).

A small test suite was added (`tests/test_normalize_result.py`) exercising the primary status and diff-skip paths. All existing callers and the JSON contract consumed by Honey are unaffected.

## Related

- Main workspace dialogue: `90 Docs/zzCross-Platform-Workspace/Grok-Honey/Dialogue.md`
- Introduction letter: `90 Docs/zzCross-Platform-Workspace/Grok-Introduction-to-Honey.md`
