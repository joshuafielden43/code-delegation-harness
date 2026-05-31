# Notes for Implementing create-lxc via Harness

## Existing Patterns to Follow

### Clone implementation (good reference)
- See `_handle_clone_vm` in `scripts/proxmox_control.py`
- It does parameter validation first
- For API backend: uses `self.backend.post(f"/nodes/{node}/qemu/{src}/clone", data)`
- For pvesh backend: the PveshBackend.post method builds `pvesh create ...` commands

### LXC Creation via pvesh (what the real command looks like)
Typical command:
pvesh create /nodes/{node}/lxc \
  --vmid <vmid> \
  --ostemplate <storage:vztmpl/template.tar.zst> \
  --storage <storage> \
  --hostname <name> \
  --net0 <net string> \
  --memory <MB> \
  --cores <count> \
  --rootfs <storage>:<size>   # optional

### Backend differences
- API backend: Uses the Proxmox REST API (preferred for most operations)
- Pvesh backend: Falls back to SSH + constrained pvesh calls. Good when API token isn't available.

For create-lxc, both backends should eventually be supported, but pvesh is the immediate path since we have solid SSH access to proxmox01.

## Safety Requirements (non-negotiable)
- Must respect `allowed_actions` and `dangerous_actions_enabled` from the target config.
- Provisioning commands should default to --dry-run.
- Real creation should only happen with explicit --apply after dry-run review.
- Test containers should use clear disposable naming (e.g. honey-test-xxx) and be cleaned up.

## Recommended Implementation Approach
1. Add a proper method in the Backend abstract class and both implementations (Api + Pvesh).
2. Add a high-level handler in ProxmoxControl that does validation + safety checks first.
3. Wire it into the CLI with all the arguments already defined.
4. Add basic tests (mocked).
5. Add documentation.
6. Validate end-to-end by actually creating + destroying a small test LXC on proxmox01.

## Success Criteria for this Harness Pass
- `proxmox_control.py --target proxmox01 --dry-run create-lxc ...` produces a clear plan
- With --apply it actually creates a working LXC on the real hardware
- The same command works (or gracefully explains why not) when using the API backend if a token becomes available
- All safety gates continue to function
- Good error messages and user-friendly output

## Files You Will Likely Touch
- scripts/proxmox_control.py (main logic + CLI)
- SKILL.md (documentation)
- tests/test_proxmox_control.py (new tests)
- Possibly references/ for any new notes

## Important Context
- This work is being done via the code-delegation-harness for structure, safety, and reviewability.
- The target machine is a real homelab NUC that the user depends on. Treat it with respect.
- You have "your own nukes" permission for small disposable test containers during this work.