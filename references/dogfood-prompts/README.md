# Dogfood Prompts

This directory contains the active, high-discipline prompts used for real dogfooding of the code-delegation-harness (gcdh) with Honey.

## Current Active Prompts

| Prompt | Purpose | Status | Notes |
|--------|---------|--------|-------|
| `tag-v2-scanner-seed-v4.md` | Original narrow `yt → youtube` validation slice | Superseded | First successful use of the strict candidate → temp-snapshot → promote gates |
| `tag-v2-scanner-seed-v5.md` | Controlled widening after v4 success (youtube + 1–2 additional small clusters) | Active / recently run | Used for the v5 run on 0.3.1. Agent performed discovery of `cli` + `cron` clusters |
| `tag-nuc-casing-micro.md` | Tiny one-off to resolve the "nuc"/"NUC" casing conflict surfaced in v5 | In flight (as of late May 2026) | Launched against `/tmp/tag-nuc-casing` |
| `tag-nuc-casing-apply.md` | Companion prompt to cleanly close the loop on the nuc decision (apply patches or document final state) | Ready | Use after the micro-pass results are reviewed |
| `proxmox-control-provisioning-v1.md` | Implement real `create-lxc` in the proxmox-control skill on live hardware (`proxmox01`) | Ready to launch | First major provisioning implementation pass via harness |
| `proxmox-control-create-lxc-notes.md` (in references/) | Supporting notes and known patterns for the create-lxc implementation | Supporting material | Created to accelerate the v1 provisioning pass |

## Usage Pattern

All prompts follow the same strict discipline:
- Candidate hunks → validate against temp snapshot only
- Only real, validated patches ever go under `patches/`
- Heavy use of `PROGRESS.json` with rich fields (`cluster_evidence`, `validation_status`, `real_target_evidence`, etc.) so the harness can produce high-signal human reports
- Honest `STATUS: PARTIAL` is the correct outcome when no real validated patches exist

These prompts are designed to be fed directly to `gcdh --task` (or referenced in the task description).

## Organization Principles

- Keep prompts narrowly scoped when possible (many-small-edits grooming style).
- Every new slice gets its own versioned file so we maintain a clear audit trail.
- Companion "apply" prompts are created when a micro-pass is expected to produce decisions that later need clean implementation.
- Old prompts are retained for historical reference but are no longer the recommended starting point.

## Current Focus (as of 2026-05-30)

Tag normalization work is the active high-leverage thread. Proxmox third-pass refinements are desired but currently deprioritized.

When the nuc micro-pass completes, the natural next step is usually to run the corresponding `apply` prompt (or move to the next small tag cluster).

## Contributing New Prompts

When creating a new prompt:
1. Base it on the latest active version (currently v5 structure + rich PROGRESS fields).
2. Keep scope tight.
3. Include the "Harness Grooming Notes Support" section so runs produce excellent reviewer artifacts.
4. Add an entry to this README.
5. Commit both the prompt and the README update.

## Follow-up Micro-Passes (New Pattern)

When a run surfaces a small open thread (e.g. a single naming conflict), we now use dedicated micro-passes + apply companions instead of bloating the next big slice.

The harness now injects additional context (via `--context` or task text) with clearer labeling for previous run artifacts. When writing follow-up prompts:

- Be extremely explicit about exact file paths from prior runs.
- Tell the agent "read these specific files first — do not broad search".
- The base harness prompt now includes guidance against wasting turns on filesystem hunting when prior run paths are provided.

This pattern (micro discovery → apply) has proven very high-signal for controlled normalization work.

## Related

- Main harness: `src/code_delegation_harness/`
- Single source of truth work log: `MEETING_OF_MODELS_TRANSCRIPT.md`
- Release process: `docs/development/release-process.md` + `RELEASE_CHECKLIST.md` (at repo root)