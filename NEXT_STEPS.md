# Next Steps for code-delegation-harness (post e4ad262)

## Immediate (Blocking)
- **TUI visibility bug**: User currently cannot see model responses in the Grok Build TUI (backend is sending them, pager/rendering is dropping them). This started during heavy harness development. 
  - Recommended: Kill current TUI session and start fresh. The work is safely on `feat/long-running-visibility`.
  - If it persists, we may need to investigate grok-pager rendering or session state.

## High Priority (Dogfood the new features)
The recent push (auto-tmux escape, --tmux flag, `scripts/gcdh-tmux`, aggressive auto-reap, strict safe live-target mutation discipline) was designed to solve the exact recurring failure mode (outer kill → partial broken state in real target → manual repair pass).

**Next concrete action**: Run a real dogfood using the *full modern pattern* to validate everything works end-to-end.

Recommended first target (low risk, good for testing recovery):
- Tag v2 scanner (controlled, no live hardware risk)
- Use the new `scripts/gcdh-tmux` or let --long-running auto-escape
- Full flags: --long-running --wait-for-completion --max-wait 86400 --output-file ... --run-name "tag-v2-resilience-test"

Alternative: Scoped continuation on Proxmox appliance provisioning now that the harness has teeth.

## Medium Term Improvements
- Capture logs inside tmux sessions (currently they go to /dev/null in the detached job).
- Add explicit `--screen` fallback when tmux is missing.
- Stronger auto-continuation: when auto-reaping a dead run, automatically offer/launch a continuation with the latest PROGRESS injected.
- Integration tests that actually exercise the tmux escape path (mocked or real).
- Make the escape behavior even smarter (detect TUI specifically via env vars and be more aggressive).
- Update remaining docs (FAQ, cli-reference, more usage examples) with the new escape + safe-workspace story.

## Philosophy Reminder
The goal is no longer "the harness sometimes works if the human babysits it."  
The goal is: a capable LLM can be given an ambitious task with the right launch command and it actually finishes (or cleanly hands off) without leaving the real target in a broken state.

We are close. The next dogfood run should prove it.

---

## Stabilization Chunk (feat/long-running-visibility, post-a22b1e6, this session)
**Date/context**: User direction: "A concrete enough chunk that you go off and write code for 10 minutes. Figure out a big chunk." + "Please do" after alignment on Codex/Honey sequencing (stabilize current PR with prompt audit artifacts + checkpoint safety as top priorities before opening clean prompt-architecture branch for real Prompt IR).

**What was delivered (real engineering, ~1h focused, not docs/polish)**:
- Extended StatusManager with first-class prompt audit surface methods (set_prompt_audit_dir, record_prompt_audit with 50-cap, getters, properties). These write into the existing durable 0600 atomic .cdh-run-*.status files → makes every model prompt observable via --status / --resume / external monitors without fs walks.
- Hardened _write_prompt_audit to also emit per-run <run_id>.manifest.json (ordered list with label, files, timestamps, chars) + richer docstring. All errors swallowed so "auditing must never kill a long-running run".
- Wired full per-probe auditing into the heart of long-running: 
  - Immediate first probe (probe-001) right after launch or --resume (before the call, so artifact exists even on early completion).
  - Every periodic while-loop probe (probe-NNN with elapsed_seconds + poll_interval in provenance).
  - This directly closes the "durable audit wiring" gap identified in the high-bar second-pass Proxmox review (the _append_audit_record that was never called).
- Enhanced launch (pass1), pass2-remediation, and _extract_weakness_profile (the inference prompt) to consistently record via the new surface + set audit dir.
- Small hygiene: --status now appends " | audits:N" for active runs that have prompt_audit_trail entries.
- All changes preserve "harness does the hard work" + resilience invariants.

**Verification performed**:
- py_compile clean on both files.
- tests/test_status_features.py (15) + test_resilience.py (24) all pass.
- Custom smoke: full exercise of StatusManager new methods (capping, dir, trail, latest), _write + manifest creation with 0600, bad-target swallow, probe-style calls. All green, no side effects on real run dirs.
- Confirmed exact baseline reset to user-stated a22b1e6 before starting edits (honoring the "checked in and pushed" covenant).

**Why this chunk**: Highest-hanging fruit outside the prior 8-requirement adversarial scope. Makes the long-running probe paths (the actual workhorses) produce durable, provenance-rich, operator-visible artifacts. Directly enables future pass-2 prompt patcher / Prompt IR (four-axis as first-class sections) on a clean branch. "Prompt power moves into typed channels/observable artifacts/deterministic assembly."

**Next per consensus**: Dogfood the full modern pattern (long-running + wait + resume + escape) on a real but safe target. Then (only after) open the prompt-architecture branch seeded from local four-axis prototype. Never skip the candid honest record + memory flush on substantial work.

**Covenants honored in this session**: Confirmed exact SHA before edits; three-bucket + candid (this entry); harness does the hard work (audit surface + manifest + wiring all in the resilient paths); no docs polishing as primary; real code + verify before claim done.

