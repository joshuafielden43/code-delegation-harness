# code-delegation-harness

A simple harness for delegating coding work to LLMs while keeping your main agent clean.

It gives you structured output + reviewable artifacts (JSON + human report + patch) even on long-running tasks, and lets you swap different backends without rewriting your top-level orchestration.

## Quick Start

```bash
# Clone and install
git clone https://github.com/joshuafielden43/code-delegation-harness.git
cd code-delegation-harness
pip install -e .

# Try it
gcdh --help
```

Works best with Grok right now, but designed to be usable with other models too.

## Why This Exists

Most agent setups mix your long-term context, style, and memory with the actual coding work. Over time that gets messy.

This tool tries to keep those concerns separate:
- Your primary agent/persona stays yours.
- Coding tasks get handed off to a focused execution environment.
- You get back clean, reviewable results instead of another giant conversation.

It also gives you the option to swap the backend harness later without having to change how you orchestrate things at the top level.

## Current Output

When you run a task with `--output-file`, you get:
- `result.json` — structured data
- `result.report.md` — human-readable review document with diffs and observations
- `result.patch` — ready-to-apply unified diff (when code changed)

The goal is simple: you stay you. The work gets done well. And you only have to review the actual result.

## Current Output (What You Actually Review)

When you delegate with `--output-file`, the harness produces:

- `result.json` — full structured data (status, files changed, summaries, errors)
- `result.report.md` — the primary document for reviewing the **end result** (clear status, per-file change descriptions with line stats and diff previews, observations from any analysis, verification steps)
- `result.patch` (when code was modified) — a ready-to-apply unified diff you can review or apply directly with `git apply`

The design goal is that you spend your time reviewing actual delivered work and collaborating on changes, not reviewing incremental proposals.

## Basic Usage

From within a Grok / agent session:

```
Delegate this task using the code-delegation-harness:

Task: Add Google-style docstrings and type hints to the `process_batch` function in src/batch.py. Do not change behavior.

Target directory: /path/to/your/project

Constraints: Follow the existing style in the file. Keep changes minimal.
```

For the best experience, have the underlying wrapper called with `--output-file` so you receive the full set of review artifacts.

### Professional CLI (`gcdh`)

**Recommended today (immediate & reliable):**

```bash
cd code-delegation-harness
chmod +x bin/gcdh
export PATH="$PWD/bin:$PATH"

gcdh --help
gcdh --quiet --task "..." --target-dir /path/to/project --output-file result.json
```

**Also available via pip:**

```bash
pip install -e .
gcdh --help
```

Both give you the full modern experience, including `--quiet` (`-q`) and `--verbose` (`-v`).

### For Agents, Sidecars & Automation (Robot-Useful)

The harness was built to be driven by other agents and sidecars:

- `--quiet` (`-q`) → minimal, clean output perfect for programmatic consumption.
- `--output-file` is strongly recommended — it produces the full machine + human artifact set.
- Structured JSON output is stable and self-describing.
- `--dry-run` + `--quiet` gives agents a cheap, safe way to preview a task before committing.
- Persistent status files + `--status` / `--resume` make long-running work observable and resumable from outside.

This design makes it a strong primitive for building reliable delegation into larger agent architectures (including future sidecar systems).

### Quiet Mode

`--quiet` (`-q`) is one of the most useful flags for both humans and agents. In quiet mode the tool only emits errors and the final artifact paths, making runs much cleaner — especially when combined with `--output-file`.

Long-running tasks are well supported:
- Use `--timeout` (seconds) and `--max-turns` to give big jobs room to breathe.
- Add `--wait-for-completion --max-wait 14400` (for example) and the wrapper will automatically poll until a background run finishes, then deliver the complete artifacts (full .json + .report.md + .patch + .run-meta.json).
- Persistent `.cdh-run-<id>.status` files are written for any run using `--run-name` or `--wait-for-completion`. These contain task snippet, run_name, timing, and state (launched / waiting / completed / max_wait_exceeded).
- Use `--status --target-dir /path` at any time to see both active and completed runs in that tree.
- Use `--resume <run-id-or-file>` to re-attach to a background run (smart short-circuit if it already finished).
- All final human review artifacts reflect the full background/resumption story when relevant.

See the `docs/` directory for usage notes, examples, and case studies.

### Dry-Run Preview Mode

Use `--dry-run` (ideally with `--quiet`) before expensive or long-running delegations. It shows exactly what would happen without executing anything or writing files:

- The full prompt that would be sent
- Resolved configuration and flags
- Expected output artifacts

This is extremely useful for agents and for humans reviewing scope.

Combine with `--quiet` for the cleanest preview output.

## Strengths

- Produces excellent, self-contained review artifacts by default
- Strong, reliable support for long-running and background tasks
- Clean handling of read-only / no-change work
- Clear error categorization and status reporting
- Full observability via persistent status files + `--status` / `--resume`

## Current Status (Production Ready)

The harness is ready for real, repeated use on production work.

It delivers clean, reviewable end results even on long-running tasks:
- Complete structured JSON
- High-signal human `.report.md` with checklists and "How to Review This Change" guidance
- Ready-to-apply `.patch`
- `.run-meta.json` for reproducibility
- Persistent status files (`.cdh-run-*.status`) with full launch → wait → completion lifecycle, queryable via `--status`

Long-running support is first-class:
- `--timeout` / `--max-turns`
- `--wait-for-completion` with automatic background recovery
- `--status` and smart `--resume` for visibility and control

The project maintains two aligned purposes:
- A practical, MIT-licensed tool for reliable coding delegation
- The primary dogfooding platform for designing clean delegation patterns for future sidecar architectures

The code in this repository is the current production version.

## Development & Contributing

Core implementation lives in `src/code_delegation_harness/harness.py` (with shims in `bin/gcdh`; `scripts/grok_delegate.py` is a legacy compatibility shim). You can also run with `python -m code_delegation_harness` after install or with PYTHONPATH=src.

See `CHANGELOG.md` for release history. Full development notes live in the upstream development tree.

## License

MIT

---

Built as a focused coding harness. The priority is useful, low-friction delegation with excellent output — for the person who still has to read, understand, and take responsibility for the final result.
