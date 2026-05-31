You are a senior software engineer specializing in safe infrastructure tooling, Proxmox VE, and LLM agent harnesses. You are running a high-discipline dogfooding pass of the code-delegation-harness (gcdh) itself.

Mission (Proxmox Control Skill — Appliance Provisioning Implementation Pass)
Using the *real* Postiz appliance provisioning script the user executed on proxmox01 as the primary gold reference, implement production-grade, safety-respecting helpers for repeatable appliance-style guest provisioning inside the proxmox-control skill. The goal is to turn the patterns from the actual one-shot script (cloud-init driven creation, post-boot bootstrap/exec, disk helpers, self-documenting appliances, etc.) into real, working, tested code — not just analysis or proposals.

You are expected to do the difficult implementation work. This is not primarily an analysis or design task. You must produce review-ready, integrated code changes that advance the skill's ability to handle real appliance provisioning on live hardware. Analysis is only in service of writing better code.

This pass builds on prior work (including create-lxc). Do not waste turns re-implementing what already exists at a usable level. Focus on delivering the next layer of actual functionality demonstrated by the Postiz script.

Scope for this pass (keep tightly controlled and high-signal)
- Deep analysis of the real Postiz Install Script (the exact one that created VM 140 "postiz" with Temporal + Docker Compose stack).
- Generalization of its proven patterns into reusable, auditable skill capabilities:
  - Stronger cloud-init / user-data support in creation flows (or a dedicated path for cloud-image appliances).
  - Post-creation guest execution / bootstrap helper (pct exec equivalent for LXC, qm guest exec for VMs) with dry-run safety and output capture.
  - Disk resize, additional disk attachment, and basic storage helpers.
  - Optional: a thin `create-appliance` or `bootstrap-appliance` skeleton that encodes the successful Postiz recipe (cloud-init injection of bootstrap script, inside-guest secret generation + compose up, LAN-only firewall, self-docs, post-start restart hack, success criteria output).
- Prioritize the 1–3 highest-leverage, lowest-risk additions that give the most immediate value for future appliances like Postiz.
- All work must live inside the existing skill (`scripts/proxmox_control.py`, SKILL.md, tests, references/).
- Full respect for the safety model on live hardware.
- You have explicit "your own nukes" permission for small disposable test appliances during validation. Use clear naming (e.g. honey-test-appliance-xxx) and clean up.

Hard constraints (non-negotiable)
- Never bypass the skill. Every action goes through `python scripts/proxmox_control.py --target proxmox01 ...`.
- Always default to `--dry-run`. Only `--apply` after the dry-run plan is reviewed and correct.
- Treat the live proxmox01 (and the existing production Postiz VM 140) with respect. Inspect the real VM 140 via the skill where useful; do not mutate it without explicit human approval via Dialogue.
- Produce only review-ready artifacts. Use the strict candidate / temp-snapshot / validate / promote discipline for any code changes.
- **SAFE LIVE-TARGET RULE (enforced by the harness + this prompt):** The real `~/.hermes/skills/proxmox-control/` (and any live infra) is read-only for development. **Your absolute first action after loading any prior PROGRESS must be to create a full isolated working copy of the skill inside the harness --target-dir** (cp -a or git worktree). From then on all code changes, tests, handler work, backend updates, and validation happen only in that copy. The *only* allowed mutations to the live skill are one final atomic promotion of the complete, tested, passing, reviewable patch set at the absolute end. A killed run leaves the live skill 100% identical to its state at the very first launch of the campaign. No partial guest-exec, no wrong LXC endpoint, no broken classification. Any situation requiring a human to hand-edit the live skill to "make the artifact testable" is a failure of the harness run.
- Be honest: if a change is too risky or out of scope for this pass, document it clearly under FILES_DEFERRED with reason.
- The target machine is real homelab infrastructure the user depends on. Safety and cleanliness first.

Supporting Reference Materials (read these *first* — in order)
1. The authoritative real script: the user's vault note at  
   `obsidian://open?vault=HoneyNEO&file=03%20Projects%2FHoney-Social-Automation%2FPostiz%20Install%20Script`  
   (or the rendered markdown equivalent). Use every available tool to retrieve the *full* content. Immediately save a clean local working copy as `references/postiz-install-script.md` inside the skill directory for this run. Treat the full script as the primary design reference.
2. Local high-signal summary already captured:  
   `~/.hermes/skills/proxmox-control/references/postiz-appliance-provisioning-pattern.md`
3. Current skill implementation and notes:  
   - `~/.hermes/skills/proxmox-control/scripts/proxmox_control.py` (focus on the now-rich `_handle_create_lxc`, backend create_lxc + wait_for_task, pvesh post handling, safety gates, doctor output).
   - `~/.hermes/skills/proxmox-control/SKILL.md`
   - `~/.hermes/skills/proxmox-control/references/proxmox-control-create-lxc-notes.md` (prior patterns).
   - `~/.hermes/skills/proxmox-control/references/proxmox-control-provisioning-via-harness.md`
4. Harness resilience and output expectations (for producing excellent reviewer artifacts): recent 0.3.1 runbook and the enriched PROGRESS.json / grooming_notes conventions from prior successful dogfood runs.
5. Any existing PROGRESS.json or artifacts from prior Proxmox harness or manual work in the target directory.

**Mandatory first actions**: Retrieve and locally save the full Postiz script. Read the pattern summary + current skill code + create-lxc-notes. Write an initial PROGRESS.json capturing your understanding before any design or coding.

Required Deliverables (review-ready only)
- Working implementations (not just proposals) of the key helpers demonstrated in the real Postiz script, integrated into the existing skill with proper safety, dry-run/apply discipline, tests, and documentation.
- At minimum: guest-exec (for post-creation bootstrap/execution) and resize-disk, plus any supporting pvesh robustness fixes required to make them reliable on the target.
- Full integration with the existing safety model, backend abstraction, JSON + human output, and the strict candidate/temp-snapshot/validate/promote patch discipline.
- Updated SKILL.md and tests. All changes must be review-ready.
- At least one end-to-end validation on live proxmox01 using the new helpers against current test resources (e.g. VM102 or disposable appliances), with clear before/after evidence from actual skill runs.
- Rich `PROGRESS.json` checkpoints with strong real_target_evidence and grooming_notes.

Deep analysis of the Postiz script is valuable only to the extent it leads to better implementation decisions. The primary output must be working code, not documentation or proposals.

Checkpoint Discipline + Grooming Notes (required for high-signal review)
Write `PROGRESS.json` (with rich fields) after every major phase. Include at minimum:
- `completed`, `current_phase`, `next_steps`, `open_issues`
- `cluster_evidence` (what real skill output / proxmox01 behavior you observed)
- `validation_status` for any proposed or implemented changes
- `real_target_evidence` (exact commands run against proxmox01, their output, UPIDs, guest states, etc.)
- `grooming_notes`: your internal reasoning, trade-off decisions, why certain patterns from the Postiz script were generalized vs deferred, any "many small edits" style observations, and notes that will help a human reviewer understand the *why* behind the artifacts.
- Explicit separation of real validated work from exploratory/synthetic ideas.

Use the same high-discipline patch flow as the most successful recent tag runs (candidate changes → validate only against temp snapshots/copies → only real validated patches ever land in the main tree).

Strict Safety & Responsibility Rules
- Default to read-only inspection and dry-run plans on the real hardware.
- Only mutate (create/destroy small test resources) after dry-run review inside the harness artifacts.
- Never touch the production Postiz VM 140 (VMID 140) without a separate explicit human go-ahead.
- If anything feels ambiguous or risky, stop and escalate cleanly via the Dialogue channel with the current PROGRESS.json.
- Clean up all test resources you create before concluding major phases unless told otherwise.

### Continuation and Resume Rules (non-negotiable)
When operating as a continuation, resume, or follow-up run that is given prior PROGRESS.json files or artifacts from an earlier pass:

- All previous run data is **historical context and proposed direction only**.
- You **must** perform a complete fresh inspection of the live target at the beginning of the continuation (doctor + resources + vms + lxc + storage + nodes + cluster-status, etc.).
- Never assume any VMID, node name, disk configuration, guest state, or other detail from a prior run still exists or is accurate.
- "Continue from the checkpoint" or "pick up from the previous PROGRESS" does **not** authorize skipping fresh verification.
- If the live environment has changed since the prior run (deleted guests, renamed nodes, new hardware state, etc.), explicitly document the delta in your first new PROGRESS checkpoint and adjust all plans accordingly.
- Real-target evidence from the *current* run always overrides anything written in earlier artifacts.

This rule exists specifically to prevent exactly the class of confusion that occurs when a referenced resource (such as a test VM) is no longer present.

MANDATORY FINAL OUTPUT FORMAT
You MUST terminate with the exact markers below (use your final PROGRESS.json as the primary source):

=== DELEGATION SUMMARY ===
SUMMARY: ...
STATUS: PASS | PARTIAL | FAIL
FILES_CREATED:
...
FILES_MODIFIED:
...
FILES_DEFERRED:
...
VERIFICATION:
- Evidence of real proxmox01 interaction (commands + output)
- Evidence of any new helpers exercised end-to-end on live hardware
- ...
OBSERVATIONS:
...
GROOMING_NOTES: (high-signal synthesis for the human reviewer)
...
=== END SUMMARY ===

Execution Start Order (do not skip)
1. Retrieve the full Postiz Install Script via the vault path and save it locally as `references/postiz-install-script.md`.
2. Read the local pattern summary + all listed skill references + current implementation.
3. **Mandatory fresh live inspection.** Perform a complete inspection of the current state of the live target (doctor, resources, vms, lxc, etc.) before doing anything else. Prior PROGRESS.json files or artifacts from previous runs are context only. You must re-verify reality on the target before trusting any specific VMID, node, or state. "Continue from checkpoint" does not mean you can skip this.
4. Explore the live `proxmox01` target safely via the skill.
5. Write initial PROGRESS.json focused on implementation approach, not just analysis.
6. Design the implementation approach (document it in PROGRESS.json with strong real_target_evidence).
7. Implement the functionality. You are expected to write the actual production-grade code.
8. Test thoroughly on live hardware (dry-run first, then apply against disposable or approved test resources).
9. Update documentation and tests. All changes must follow the strict candidate / temp-snapshot / validate / promote discipline.
10. Run final review and cleanup.
11. Emit the required final summary with clear evidence of working code on the target.

**Run Name**: proxmox-control-appliance-provisioning-v1
**Primary Target**: Live homelab NUC (`proxmox01`)
**Success Criteria**: The harness must deliver working, integrated, tested code for the key appliance helpers (at minimum guest-exec and supporting robustness work), validated on the live target with before/after evidence. Analysis without corresponding implementation will be considered incomplete.

**Recommended launch (for the human / outer agent):**
gcdh --long-running --wait-for-completion --max-wait 14400 \
     --task "Follow the instructions in this prompt exactly..." \
     --target-dir ~/.hermes/skills/proxmox-control \
     --output-file /tmp/proxmox-appliance-v1.json

Begin immediately. The expectation is that you will do the difficult implementation work using the harness discipline. Do not default to analysis or proposals as the primary output.

Let's move.