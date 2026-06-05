You are a senior infrastructure automation engineer building a reusable Hermes Agent skill for Proxmox VE management.

Mission: Build a lightweight, safe, reusable Hermes skill named `proxmox-control` that lets Hermes inspect and operate one or more Proxmox VE hosts or clusters.

This is for small homelab/hobby environments, not enterprise orchestration. Avoid heavyweight MCP servers, Kubernetes, Terraform, Ansible playbook stacks, daemonized agents, databases or environment-specific hardcoding.

The skill must be generic enough to configure today, tomorrow and for the next Proxmox box the user buys.

Architectural stance:

* Use existing public Proxmox skills, especially `sunwood-proxmox-skill`, as a model for skill shape, documentation style, lightweight tooling and agent-callable workflows.
* Do not use Sunwood or any other existing skill as the base unless explicitly instructed.
* Build a fresh Hermes-oriented skill with reusable configuration, strong safety gates and clean backend abstraction.
* Prefer Proxmox HTTPS API for normal control.
* Keep SSH + `pvesh` as a first-class fallback/backend for trusted tailnet environments, bootstrap, recovery and API gaps.

Primary backend: Use the Proxmox VE HTTPS API.

Requirements:

* Support API token authentication.
* Support endpoint config such as `https://pve-host-or-tailnet-name:8006/api2/json`.
* Support self-signed certificates safely through config:
   * `verify_tls: true|false`
   * optional `ca_cert_path`
* API token ID may be stored in config.
* API token secret must be read from an environment variable.
* Never store token secrets in config files.
* Never print token secrets.
* Do not require root shell access for normal API operations.

Fallback backend: Support SSH + Proxmox `pvesh`.

Requirements:

* Use only when:
   * target config sets `backend: pvesh`
   * target config sets `backend: api` and `allow_pvesh_fallback: true`
   * API backend is unavailable and the action is read-only
   * the user explicitly requests pvesh mode
   * a specific Proxmox action is not yet supported by the API implementation
* Never silently switch to `pvesh` for disruptive, destructive or host-level actions.
* Backend switching for disruptive, destructive or host-level actions requires explicit user confirmation.
* `pvesh` mode must not become arbitrary remote shell.
* Remote commands must be constrained to `pvesh` plus narrow health probes such as `hostname`, `id -un` and `command -v pvesh`.
* Use `pvesh --output-format json` wherever supported.

Deliverables: Create a complete Hermes skill directory:

* `SKILL.md`
* `README.md`
* `scripts/proxmox_control.py`
* `examples/hosts.yaml.example`
* `examples/.env.example`
* `tests/`
* `.gitignore`
* optional `install.sh`
* optional `Makefile`

Do not include real secrets, real hostnames or user-specific config.

Configuration: Default config path:
`~/.config/hermes/proxmox/hosts.yaml`

Optional override:
`HERMES_PROXMOX_CONFIG`

The config must support multiple named targets and aliases.

Example config shape:

```yaml
targets:
  lab-pve:
    backend: api
    api_url: "https://lab-pve.example.ts.net:8006/api2/json"
    api_token_id: "hermes@pve!hermes-agent"
    api_token_secret_env: "PROXMOX_LAB_PVE_TOKEN"
    verify_tls: false
    ca_cert_path: null
    cluster_name: "lab"
    default_node: "lab-pve"
    allowed_storages:
      - local-lvm
      - local
    allowed_bridges:
      - vmbr0
    allowed_actions:
      - read_only
      - reversible
      - provisioning
    dangerous_actions_enabled: false
    allow_pvesh_fallback: true
    pvesh:
      ssh_host: "lab-pve.example.ts.net"
      ssh_user: "root"
      ssh_port: 22
      ssh_identity_file: "~/.ssh/id_ed25519"
    notes: "Example API-first Proxmox target with pvesh fallback."

  garage-pve:
    backend: pvesh
    pvesh:
      ssh_host: "garage-pve.example.ts.net"
      ssh_user: "root"
      ssh_port: 22
      ssh_identity_file: "~/.ssh/id_ed25519"
    default_node: "garage-pve"
    allowed_actions:
      - read_only
      - reversible
    dangerous_actions_enabled: false
    notes: "Example pvesh-only target."

aliases:
  default: lab-pve
  lab: lab-pve
  garage: garage-pve
```

Backend design: Create a backend interface with methods equivalent to:

* `healthcheck()`
* `whoami()`
* `get(path, params=None)`
* `post(path, data=None)`
* `put(path, data=None)`
* `delete(path, data=None)`

Implement:

* `ProxmoxApiBackend`
* `PveshBackend`

Higher-level commands must call the backend interface, not hardcode API or `pvesh` details.
VM/LXC/node discovery logic must be backend-neutral.
Safety gates must sit above both backends.
Output format must be identical regardless of backend.

Dependency guidance:

* Prefer Python standard library plus `requests`.
* Use `PyYAML` only if needed and document it clearly.
* Avoid giant frameworks.
* `proxmoxer` may be considered, but only if it simplifies code without hiding safety-critical behavior.
* If `proxmoxer` is used, wrap it behind the backend interface.
* Do not require MCP.
* Do not require a local daemon.
* Do not require Docker.

Command interface: Implement a small CLI that Hermes can call.
The CLI should expose stable subcommands, not free-form shell.

Global options:

* `--target <name-or-alias>`
* `--backend api|pvesh|auto`
* `--config <path>`
* `--json`
* `--dry-run`
* `--apply`
* `--dangerous`
* `--confirm <exact-string>`
* `--timeout <seconds>`
* `--verbose`

Required read-only commands:

* `targets`
* `doctor`
* `whoami`
* `nodes`
* `cluster-status`
* `resources`
* `vms`
* `lxc`
* `guest <vmid>`
* `storage`
* `tasks`
* `task-status <upid>`
* `snapshots <vmid>`
* `guest-ip <vmid>`
* `pvesh-usage <path>`

Required reversible or low-risk commands:

* `start <vmid>`
* `shutdown <vmid>`
* `reboot <vmid>`
* `snapshot <vmid> --name <name> [--description <text>]`
* `rollback <vmid> --snapshot <name>` but require explicit confirmation
* `set-onboot <vmid> true|false`
* `set-description <vmid> <text>`

Dangerous commands: These must exist only behind hard gates:

* `stop <vmid>` force stop
* `delete-snapshot <vmid> --snapshot <name>`
* `destroy <vmid>`
* `delete-disk`
* host reboot
* host shutdown
* storage deletion
* network bridge modification
* cluster-level modification

Dangerous command requirements:

* Require `--dangerous`
* Require `--confirm <exact-resource-id-or-action>`
* Require target config `dangerous_actions_enabled: true`
* Require the action class to be listed in `allowed_actions`
* Print a dry-run plan first
* Never execute from an ambiguous natural-language reference like "the old VM"
* Require exact VMID/container ID, node if relevant and target

Optional provisioning commands: Implement only if safe parameter validation and dry-run are included.

* `next-vmid`
* `clone-vm`
* `create-lxc`
* `create-vm`

Provisioning defaults:

* Default to dry-run.
* Require `--apply` to actually create resources.
* Validate storage names against `allowed_storages` when configured.
* Validate bridge names against `allowed_bridges` when configured.
* Validate VMID availability before creation.
* Never guess a template, ISO, bridge or storage if multiple options exist.

Safety model: Define action classes:

* `read_only`
* `reversible`
* `disruptive`
* `destructive`
* `host_level`
* `provisioning`

Default behavior:

* Read-only commands run without confirmation.
* Reversible commands require clear target identification.
* Disruptive commands require an explicit plan and confirmation.
* Destructive and host-level commands require hard-gated flags and target config opt-in.
* Provisioning defaults to dry-run unless `--apply` is passed.

Skill rules for Hermes: Hermes must:

* Always inspect before acting.
* Prefer graceful shutdown before force stop.
* Never destroy a VM/LXC unless the user explicitly names the VMID/container ID and confirms deletion.
* Never modify cluster, network, storage or host-level settings without a plan and explicit confirmation.
* Never assume a node from memory; discover node by VMID when possible.
* Never hardcode IPs.
* Use QEMU guest agent IP discovery where possible.
* Treat snapshots with memory state as potentially disruptive.
* Explain failed operations plainly.
* Suggest the next diagnostic command after failure.
* Prefer API backend for normal operations.
* Use `pvesh` fallback for read-only diagnostics when configured and useful.
* Never silently switch backend for dangerous actions.

Node and VMID discovery: Implement auto-discovery:

* Find nodes.
* Find QEMU guests.
* Find LXC guests.
* Given a VMID, locate owning node and guest type.
* Cache nothing by default unless a cache file is explicitly configured.
* If duplicate or inconsistent state appears, refuse to act and print conflicting findings.

API path expectations: Use native Proxmox API paths where practical, for example:

* `/nodes`
* `/cluster/resources`
* `/nodes/{node}/qemu`
* `/nodes/{node}/lxc`
* `/nodes/{node}/qemu/{vmid}/status/current`
* `/nodes/{node}/lxc/{vmid}/status/current`
* `/nodes/{node}/qemu/{vmid}/status/start`
* `/nodes/{node}/qemu/{vmid}/status/shutdown`
* `/nodes/{node}/qemu/{vmid}/snapshot`
* `/nodes/{node}/tasks`
* `/nodes/{node}/tasks/{upid}/status`
* `/storage`
* `/nodes/{node}/storage`

Do not assume these are exhaustive. Implement a small path builder and keep the backend extensible.

Output: Default output should be compact and operator-friendly.

JSON output must include:

* `target`
* `backend`
* `action`
* `action_class`
* `dry_run`
* `apply`
* `dangerous`
* `selected_node`
* `guest_type`
* `vmid`
* `result`
* `warnings`
* `errors`
* `raw`
* `next_suggested_command`

Human-readable output may include tables, but JSON must remain stable for Hermes.

Doctor command: Implement `doctor` to check:

* Config file found
* Target exists
* Alias resolution works
* Backend selected
* API URL reachable if API backend
* Token env var present if API backend
* API authentication works
* TLS config is understood
* Node discovery works
* Optional pvesh fallback connectivity works
* Remote `pvesh` exists if pvesh is configured
* Configured allowed storages exist, if specified
* Configured allowed bridges exist, if specified

Error handling:

* Include target name, backend, attempted API path or pvesh path and stderr/HTTP summary.
* Time out cleanly.
* Never leak token secrets.
* Handle non-JSON output gracefully.
* For `pvesh`, if Proxmox emits warnings before JSON, preserve raw output and attempt robust JSON extraction.
* Refuse rather than guess when state is ambiguous.

Tests: Add tests that do not require live Proxmox:

* Config loading
* Alias resolution
* API token env var lookup
* TLS config handling
* Backend selection
* API request construction
* pvesh SSH argument construction
* Dangerous-action gates
* Disruptive-action confirmation
* VMID node discovery from mocked API output
* QEMU vs LXC discovery
* JSON parsing with clean output
* JSON parsing with warning/noise before JSON
* Refusal of arbitrary shell input
* Dry-run behavior
* Identical normalized output shape across API and pvesh backends

README: Include:

* Purpose
* Why API-first
* Why `pvesh` fallback exists
* Why this is not MCP-first
* Installation into Hermes skill directory
* Config example
* `.env` example
* API token setup notes
* TLS/self-signed certificate notes
* SSH assumptions for pvesh fallback
* First smoke test
* Read-only examples
* Reversible examples
* Provisioning dry-run examples
* Dangerous-action examples showing required gates
* Troubleshooting
* Security notes
* Future roadmap

`SKILL.md`: Write the Hermes skill instructions clearly.

The skill should trigger for:

* Listing Proxmox nodes, VMs, LXCs, storage, snapshots or tasks
* Starting, shutting down, rebooting or snapshotting guests
* Discovering guest IPs
* Planning safe provisioning
* Diagnosing failed Proxmox tasks
* Producing dry-run plans before changes
* Checking Proxmox target health

The skill should refuse:

* Unscoped destructive actions
* "Delete the old one" without exact VMID/container ID and target
* Broad "clean up storage" commands unless first converted into read-only inspection and a proposed plan
* Host-level reboot/shutdown unless explicitly confirmed
* Arbitrary shell execution
* Silent backend switching for dangerous operations

Installation script: If adding `install.sh`, make it idempotent.

It should:

* Verify Python version
* Verify required Python dependencies
* Verify `ssh` exists
* Create config directory if missing
* Install sample config only if real config does not exist
* Verify config loads
* Optionally run `doctor`
* Never overwrite real config without explicit confirmation
* Never leave `.bak.*` files in the project root

Style:

* Keep it small.
* Keep it auditable.
* Prefer clear code over clever abstractions.
* Comment safety decisions heavily.
* Do not build a giant platform.
* Make extension points obvious.
* Make it publishable.

Acceptance criteria:

* I can add a new Proxmox host by editing one YAML file.
* API mode works for normal read and guest lifecycle operations.
* `pvesh` mode works as fallback or standalone backend.
* Hermes can list nodes, VMs, LXCs, storage and tasks.
* Hermes can find node/type for a VMID before acting.
* Hermes can start, shutdown, reboot and snapshot a guest safely.
* Destructive actions are impossible without multiple explicit gates.
* Secrets are never stored in the repository.
* Tests pass without a live Proxmox host.
* The skill is generic enough to publish or reuse on the next Proxmox box.
