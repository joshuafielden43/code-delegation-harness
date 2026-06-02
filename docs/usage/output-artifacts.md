# Output Artifacts

When you run a task with `--output-file <path>`, the harness produces a set of artifacts designed to be easy to review and act on.

## Primary Artifacts

### `<name>.json`
The main structured result. Contains:
- Summary of what was accomplished
- List of files created, modified, and deleted
- Change summaries and observations
- Any errors or warnings
- Metadata (task, model, timing, run ID, etc.)

This is the machine-readable output. Good for agents and automation.

### `<name>.report.md`
The **primary document you should read** as a human.

It is written to be review-friendly and includes:
- Clear status
- Per-file change descriptions with line counts
- Diff previews where relevant
- Observations
- A "How to Review This Change" checklist

This is the document Honey (or any reviewer) should open first.

### `<name>.patch` (when applicable)
A ready-to-apply unified diff of all changes made.

You can review it and apply with:
```bash
git apply <name>.patch
```

### `<name>.run-meta.json`
Reproducibility information:
- Exact task, target directory, model, and flags used
- Timing information
- Run ID
- Whether the run waited for background completion, etc.

Useful for auditing and reproducing runs later.

## Status Files

In addition to the artifacts above, the harness writes persistent status files in the target directory:

- `.cdh-run-<id>.status`

These are used for:
- `--status` queries
- `--resume` functionality
- Long-running / background task coordination

They are deliberately written with restrictive permissions (0600) for privacy.

## When No `--output-file` Is Provided

You will still get the structured result printed to stdout, plus a status file in the target directory. However, you will **not** receive the `.report.md` or `.patch` files.

For any real work, we strongly recommend using `--output-file`.
