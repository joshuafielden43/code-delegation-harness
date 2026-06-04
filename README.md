# code-delegation-harness

A model-agnostic harness for delegating coding work to any coding CLI (Claude Code, Grok Code, Codex, Agy) while keeping your primary agent or orchestration layer clean.

Produces structured, reviewable artifacts plus a canonical build attempt trace per run. Normalises prompts upfront, verifies output against a typed artifact manifest, and runs adversarial remediation passes grounded in real filesystem evidence — not model self-reporting.

## Quick Start

```bash
pip install git+https://github.com/joshuafielden43/code-delegation-harness.git
gcdh --help
```

For the Anthropic-backed intake normaliser:

```bash
pip install "git+https://github.com/joshuafielden43/code-delegation-harness.git#egg=code-delegation-harness[intake]"
export ANTHROPIC_API_KEY=...
```

## What It Does

Every `gcdh` invocation goes through four stages:

1. **Intake gate** — detects whether the prompt is human or AI-structured; if human, normalises it via an orchestrator model (Anthropic API or CLI fallback); extracts a typed artifact manifest; pre-generates an adversarial attack frame. One API call, done once upfront.

2. **Hygiene stanza** — appends a fixed, version-pinned block of universal engineering standards to every normalised prompt before the execution CLI runs.

3. **Execution + manifest diff** — runs the coding CLI; then does a real filesystem scan against the expected artifact list. Missing artifacts become explicit attack targets.

4. **Attack loop + smoke tests** — if pass 1 underperforms (`--auto-remediate`), runs a bounded adversarial second pass targeting actual gaps. T1/T2/T3 smoke tests verify existence, importability, and interface conformance.

Every run produces a **build attempt trace** — a YAML record of the full lifecycle: intent, normalisation, manifest, run records with SHA-256 output digests, attack critique, verdict, and smoke tier.

## Output Artifacts

With `--output-file`:

| Artifact | Contents |
|---|---|
| `result.json` | Full structured result + `intake_status`, `manifest_found/missing`, `smoke`, `build_attempt_trace` |
| `result.report.md` | Human-scannable review doc: status, per-file diffs, build trace path, intake status |
| `result.patch` | Ready-to-apply unified diff (when code was modified) |
| `result.run-meta.json` | Reproducibility metadata (flags, timing, run ID) |
| `{research-dir}/build-attempts/{id}.yaml` | Canonical build attempt trace |
| `{research-dir}/{run-id}-pass1-stdout.txt` | Full CLI stdout (SHA-256 in trace) |

## Basic Usage

```bash
# Simple delegation
gcdh --task "Add type hints to src/auth.py" \
     --target-dir /path/to/project \
     --output-file result.json

# With intake normalisation (Anthropic backend auto-detected from ANTHROPIC_API_KEY)
gcdh --task "Add OAuth2 login" \
     --target-dir /path/to/project \
     --output-file result.json \
     --auto-remediate --iterations 2

# Preview without executing
gcdh --task "..." --target-dir /path --dry-run

# Long-running ambitious work (auto-escapes from TUI/CI wrappers via tmux)
gcdh --long-running --wait-for-completion --max-wait 86400 \
     --task "..." --target-dir /path --output-file result.json \
     --auto-remediate --iterations 2 --run-name "my-ambitious-job"
```

## Intake Gate

The intake gate runs before every CLI invocation (bypassed by `--skip-normalization`).

- **Detection**: ~5-line schema validator distinguishes human vs AI-structured prompts. AI-structured passes through unchanged.
- **Normalisation**: rewrites human prompts into explicit, structured form via the orchestrator model.
- **Manifest extraction**: produces a typed artifact list (`file`, `function`, `class`, `interface`, `config`, `library`). Injected into the execution prompt to reduce drift.
- **Attack frame pre-gen**: adversarial critique template generated upfront, seeding the attack loop.

On any failure the harness degrades gracefully — raw prompt passes through, `intake_status: degraded` in the result. Never aborts a run.

### Orchestrator backends

| Provider | How | Requires |
|---|---|---|
| `auto` (default) | Anthropic API if `ANTHROPIC_API_KEY` set, else CLI | — |
| `anthropic` | Anthropic API, native `tool_use` | `pip install cdh[intake]` |
| `cli` | Execution CLI subprocess | nothing |

```bash
gcdh --orchestrator-provider anthropic --orchestrator-model claude-opus-4-8 ...
gcdh --orchestrator-provider cli ...        # offline/air-gapped
gcdh --skip-normalization ...               # bypass intake + stanza entirely
```

### Normalization prompt versioning

The system prompt used for normalisation lives in `src/code_delegation_harness/prompts/normalization_v1.0.txt`. Edit it to improve quality without changing Python source. The version is recorded in every trace under `normalized_via.prompt_version`.

## Hygiene Stanza

A fixed block of five universal engineering standards appended to every normalised prompt:

- Produce auditable artifacts
- Respect interface contracts
- Iterate rather than rewrite
- Leave a decision note for non-obvious choices
- Declared dependencies only

Version-pinned (`v1.0`). Portability-linted — any stanza referencing a specific project, file, or script fails `assert_stanza_portable()`. Domain-specific module slots reserved for Phase 6.

```bash
gcdh --no-hygiene              # skip stanza (debugging only)
gcdh --stanza-modules base     # explicit module selection (default)
```

## Manifest Diffing + Smoke Tests

After execution, the harness scans the target directory against the expected artifact manifest:

- `manifest_found` / `manifest_missing` in result JSON — ground truth, not model self-reporting
- Missing artifacts are injected as `spec_coverage` weakness items in the attack prompt
- **T1** — artifact exists on disk
- **T2** — `python -c 'import <module>'` exits 0
- **T3** — public names from spec description present in AST

Smoke tier (`null | t1_exists | t2_compiles | t3_interface`) in `verdict.smoke_tier` and the trace.

## Attack Loop

```bash
gcdh --auto-remediate --iterations 2 ...
```

`--iterations N` = total pass cap (1 original + N-1 attack passes). Default 2. The attack prompt is built from:
- LLM-inferred weakness profile from pass 1
- Real manifest gaps (filesystem scan)
- Pre-generated attack frame from intake

Pass 2 uses `--yolo` (unattended). The attack prompt is persisted as `<stem>.pass2.prompt.txt` for review.

## Confirmation Loop

```bash
gcdh --confirm ...
```

Before the CLI runs, shows normalised intent and expected artifact list. Accepts one correction, re-normalises, re-shows. Hard cap: 2 rounds, proceeds regardless. Corrections captured in trace for tuning.

Off by default — never interrupts automated pipelines.

## Build Attempt Trace

Every run writes a YAML trace to `{research-dir}/build-attempts/{id}.yaml`:

```yaml
id: 20260604T011812-0e7118be
status: complete
intent_raw: "add login feature"
intent_detection: human
was_normalized: true
intent_normalized: "TASK: Add OAuth2 login to src/auth.py ..."
hygiene_stanza_version: v1.0
manifest:
  expected: [{type: file, name: auth.py, ...}]
  found: [auth.py]
  missing: []
runs:
  - run_id: 1
    cli: grok-build
    exit: clean
    stdout_digest: deadbeef...
verdict:
  outcome: passed
  smoke_tier: t2_compiles
```

Traces are 0600. Purge with `--prune-research [N]` (default 7 days).

## Operational Commands

```bash
gcdh --status --target-dir /path         # active + completed runs
gcdh --resume <run-id>                   # re-attach to background run
gcdh --reap-dead --target-dir /path      # mark silent runs crashed
gcdh --prune 7 --target-dir /path        # prune old status files
gcdh --prune-research 7 --target-dir /path   # prune traces + stdout/stderr
```

## Documentation

- [CLI Reference](docs/usage/cli-reference.md)
- [Output Artifacts](docs/usage/output-artifacts.md)
- [Architecture](docs/advanced/architecture.md)
- [For Agents and Sidecars](docs/usage/for-agents-and-sidecars.md)
- [Operational Runbook](docs/operations/runbook-resilience.md)

## Development

```bash
git clone https://github.com/joshuafielden43/code-delegation-harness
pip install -e ".[intake]"
python -m pytest tests/
```

153 tests. All modules have dedicated test files.

## License

MIT

---

Built as a focused coding harness. The priority is reliable delegation with excellent output and full auditability — for the person who still has to read, understand, and take responsibility for the final result.
