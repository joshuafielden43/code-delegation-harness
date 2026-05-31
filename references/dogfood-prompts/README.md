# Dogfood Prompts

This directory contains the active, high-discipline prompts used for real dogfooding of the code-delegation-harness (gcdh) with Honey.

## Current Active Prompts

| Prompt | Purpose | Status | Notes |
|--------|---------|--------|-------|
| `tag-v2-scanner-seed-v4.md` | Original narrow `yt → youtube` validation slice | Superseded | First successful use of the strict candidate → temp-snapshot → promote gates |
| `tag-v2-scanner-seed-v5.md` | Controlled widening after v4 success (youtube + 1–2 additional small clusters) | Active / recently run | Used for the v5 run on 0.3.1. Agent performed discovery of `cli` + `cron` clusters |
| `tag-nuc-casing-micro.md` | Tiny one-off to resolve the "nuc"/"NUC" casing conflict surfaced in v5 | In flight (as of late May 2026) | Launched against `/tmp/tag-nuc-casing` |
| `tag-nuc-casing-apply.md` | Companion prompt to cleanly close the loop on the nuc decision (apply patches or document final state) | Ready | Use after the micro-pass results are reviewed |
| `proxmox-control-provisioning-v1.md` | Implement real `create-lxc` in the proxmox-control skill on live hardware (`proxmox01`) | Historical | First major provisioning implementation pass (largely complete via prior work + manual hardening) |
| `proxmox-control-appliance-provisioning-v1.md` | Next-layer appliance provisioning patterns driven by the *real* Postiz one-shot script (VM 140 on proxmox01). Cloud-init, guest-exec/bootstrap, disk helpers, `create-appliance` skeleton, etc. Builds on the now-mature create-lxc surface. | **Active / Ready to launch immediately** | Current highest-leverage Proxmox dogfood. Uses the actual user script as primary reference. Strict live-hardware discipline + rich grooming notes expected. |
| `proxmox-control-create-lxc-notes.md` (in references/) | Supporting notes and known patterns for the create-lxc implementation | Supporting material | Historical patterns from the first provisioning pass |

## Usage Pattern

All prompts follow the same strict discipline:
- Candidate hunks → validate against temp snapshot only
- Only real, validated patches ever go under `patches/`
- Heavy use of `PROGRESS.json` with rich fields (`cluster_evidence`, `validation_status`, `real_target_evidence`, etc.) so the harness can produce high-signal human reports
- Honest `STATUS: PARTIAL` is the correct outcome when no real validated patches exist

These prompts are designed to be fed directly to `gcdh --task` (or referenced in the task description).

### Recommended Launch Command for Real Dogfood Runs (the full check-in-worthy pattern)

```bash
gcdh \
  --long-running \
  --wait-for-completion \
  --max-wait 86400 \
  --output-file /tmp/dogfood-$(date +%Y%m%d-%H%M).json \
  --run-name "your-important-work" \
  --quiet \
  --task "Follow this prompt exactly..." \
  --target-dir /tmp/your-isolated-workspace-for-this-run
```

**This is now the mandatory pattern for anything worth checking in.**

Key behaviors that make it actually work from inside constrained environments (TUI, short wrappers, etc.):
- `--long-running` auto-bumps limits + injects the ruthless job-to-the-end + anti-stale language.
- In hostile launchers (this TUI etc.), the harness **auto-escapes** the whole job into a detached tmux session so the outer 300s kill cannot reach it.
- At every new `--long-running` launch the harness **auto-reaps** any dead prior runs (heartbeat + PID probe) so previous crashes do not leave the live target polluted.
- The prompt (and the Proxmox-specific ones) now **require** as the very first action: create an isolated working copy of the live target inside `--target-dir`. No direct mutations to the real skill/infra until one final atomic promotion of a complete tested set.
- `--output-file` + `--run-name` + `--quiet` for clean artifacts and observability.

Use the full pattern. This is what lets a capable LLM actually finish ambitious dogfood without forcing manual repair passes on the target afterward.

## Serious Reflection on Past Process Issues (as of 2026-05-31)

This section exists because the project drifted for too long:
- Too much direct manual implementation on dogfood targets instead of forcing the harness to do the work.
- Prompt language was allowed to soften over iterations (analysis-first drift instead of ruthless implementation-first).
- The `--long-running` flag existed in code but was under-documented, under-recommended, and not used on the actual failing runs for far too long.
- Every supporting file (docs, tests, examples, runbooks) required excessive justification instead of being added proactively when the user asked.

Going forward the default posture is:
- When the user says "add the files" or "document this" → do it quickly and cleanly.
- For any real dogfood, default to using `--long-running` + proper output artifacts.
- The harness prompt and launch patterns must stay ruthlessly focused on "complete the job end-to-end with fresh verification."

These are process anti-patterns we will not repeat.

### Additional Process Commitments (2026-06+)
- When the user says "add the files" or "document X", do it promptly and cleanly instead of requiring justification for each one.
- The default assumption for any real dogfood run is the full pattern: `--long-running + --wait-for-completion + --max-wait 86400 + --output-file + (auto-escape + auto-reap + safe isolated workspace discipline)`.
- The harness itself now actively helps escape the very constrained environments it is often developed inside, so that the "actual LLM that can do the fucking job" can use it without constant outer intervention or leaving broken live targets.

These anti-patterns (drift, prompt softening, manual repair passes on dogfood targets after harness deaths) are closed. The tree is now in a state worth checking the fuck in and checking the fuck out.
- We will run regular "Meeting of Models" style self-audits on the harness and its usage patterns instead of waiting for the user to surface every issue.
- The harness prompt and launch patterns will stay ruthlessly implementation-focused. Analysis is a tool, not the goal.

## Organization Principles

- Keep prompts narrowly scoped when possible (many-small-edits grooming style).
- Every new slice gets its own versioned file so we maintain a clear audit trail.
- Companion "apply" prompts are created when a micro-pass is expected to produce decisions that later need clean implementation.
- Old prompts are retained for historical reference but are no longer the recommended starting point.

## Current Focus (as of 2026-05-31)

- **Proxmox appliance provisioning (highest priority right now)**: `proxmox-control-appliance-provisioning-v1.md` — ready for immediate launch against live proxmox01 using the real Postiz script as the primary reference. This is the active dogfood thread while hardware access and user momentum are fresh.
- Tag normalization work (v5 + nuc micro/apply companions) remains available for parallel or follow-up slices.

Launch the new Proxmox appliance prompt next. The skill surface (create-lxc + supporting helpers) has been deliberately hardened in parallel to give the harness a strong foundation.

## Contributing New Prompts

When creating or evolving a new prompt:
1. Base it on the latest active version, but be extremely careful about softening language over time.
2. The core mission must remain "you will implement production-grade code using the harness discipline", not drift into "do excellent analysis and propose things".
3. Keep scope tight.
4. Include the "Harness Grooming Notes Support" section so runs produce excellent reviewer artifacts.
5. Explicitly protect the "never rely on cached data" and "you must do the difficult implementation work" rules.
6. Add an entry to this README.
7. Commit both the prompt and the README update.

**Warning from experience**: It is easy to accidentally neuter a prompt by evolving the mission to match work that was done directly outside the harness. This leads to weaker runs. When in doubt, restore the original direct, imperative framing.

## Follow-up Micro-Passes and Continuations (New Pattern)

When a run surfaces a small open thread (e.g. a single naming conflict), we now use dedicated micro-passes + apply companions instead of bloating the next big slice.

The harness now injects additional context (via `--context` or task text) with clearer labeling for previous run artifacts. When writing follow-up or continuation prompts:

- Be extremely explicit about exact file paths from prior runs.
- Tell the agent "read these specific files first — do not broad search".
- The base harness prompt now includes guidance against wasting turns on filesystem hunting when prior run paths are provided.
- **Critical rule for continuations/resumes**: Prior PROGRESS.json and artifacts are context + proposed direction only. The agent must still perform a full fresh live inspection (doctor, resources, current guests, etc.) before trusting or acting on any specific state from a previous run. "Never rely on cached data" is non-negotiable, even when picking up from a checkpoint.

### Standing Continuation / Resume Rule (applies to all future prompts)

All prompts that support or expect long-running or resumable work must include a dedicated "Continuation and Resume Rules" section with the following core language (or stronger):

> When operating as a continuation or resume:
> - All prior run data is historical context and proposed direction **only**.
> - You must perform a complete fresh inspection of the live target before trusting any VMID, node, state, or plan from a previous PROGRESS.json.
> - "Continue from the checkpoint" does **not** mean you can skip re-verification.
> - Explicitly document any drift (deleted resources, changed environment, etc.) in your first new checkpoint.

This rule exists to prevent agents from acting on stale references (e.g. a test VM that no longer exists) and the resulting confusion in review.

This pattern (micro discovery → apply) has proven very high-signal for controlled normalization work.

## Related

- Main harness: `src/code_delegation_harness/`
- **For long-running Proxmox / skill-extension dogfood**: Always launch with `--long-running --wait-for-completion --output-file ... --run-name "..."`. The harness now has baked-in ruthless "anti-stale + job-to-the-end + keep-driving" language + dynamic PROGRESS injection on every probe. This is the configuration that gives high confidence of full end-to-end success (impl + tests + promotion) on live hardware without babysitting.
- Single source of truth work log: `MEETING_OF_MODELS_TRANSCRIPT.md`
- Release process: `docs/development/release-process.md` + `RELEASE_CHECKLIST.md` (at repo root)