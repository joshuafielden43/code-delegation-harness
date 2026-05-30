# Proposed Complete Documentation Structure

This document outlines every document the Code Delegation Harness should eventually have, based on the current project skeleton and its positioning as a universal, production-grade CLI tool for delegating coding work to LLMs (with excellent support for agents and sidecars).

The goal is to be exhaustive but realistic. Documents are grouped by priority and purpose.

---

## Root-Level Documentation (Standard OSS Expectations)

These should live in the repository root:

- `README.md` — Primary landing page and quick overview (already exists, needs ongoing maintenance)
- `CHANGELOG.md` — Release history (exists)
- `LICENSE` — Legal (exists)
- `CONTRIBUTING.md` — How to contribute (exists but minimal — needs significant expansion)
- `CODE_OF_CONDUCT.md` — Community standards (missing)
- `SECURITY.md` — How to report security issues (missing)
- `SUPPORT.md` — Where to get help (optional but recommended)
- `.github/FUNDING.yml` — Sponsorship links (optional)
- `CITATION.cff` — For academic / citation use (nice to have)

---

## docs/ Structure (Recommended)

```text
docs/
├── getting-started/
│   ├── installation.md                 # Primary installation guide (created)
│   └── quickstart.md                   # 5-minute "hello world" example
│
├── usage/
│   ├── basic-usage.md                  # Core concepts and simple examples
│   ├── cli-reference.md                # Complete --help style reference for all flags
│   ├── output-artifacts.md             # Deep dive into .json, .report.md, .patch, .run-meta.json
│   ├── long-running-and-background-tasks.md
│   ├── quiet-mode-and-automation.md
│   └── for-agents-and-sidecars.md      # Critical document given project positioning
│
├── examples/
│   ├── index.md
│   ├── basic-delegation.md
│   ├── long-running-task.md
│   └── agent-driven-workflow.md
│
├── advanced/
│   ├── architecture.md                 # How the harness actually works
│   ├── status-files-and-observability.md
│   ├── prompt-construction.md          # For advanced users who want to understand the prompt
│   ├── custom-workflows.md
│   └── integration-patterns.md         # How to embed this in larger agent systems
│
├── development/
│   ├── contributing.md                 # Detailed contribution guide (can link to root CONTRIBUTING.md)
│   ├── development-setup.md
│   ├── architecture.md                 # Internal design (deeper than the user-facing one)
│   ├── testing.md
│   └── release-process.md
│
├── faq.md
├── troubleshooting.md
├── comparison.md                       # How this differs from other tools (Claude Code, Aider, Cursor, etc.)
└── roadmap.md
```

---

## Priority Classification

### Must Have for a Professional v1 Public Release

- README.md (core)
- CHANGELOG.md
- CONTRIBUTING.md (expanded)
- CODE_OF_CONDUCT.md
- SECURITY.md
- docs/installation.md (done)
- docs/quickstart.md
- docs/usage/basic-usage.md
- docs/usage/cli-reference.md
- docs/usage/output-artifacts.md
- docs/usage/for-agents-and-sidecars.md
- docs/faq.md
- docs/troubleshooting.md

### Should Have Soon After

- docs/getting-started/quickstart.md
- docs/advanced/architecture.md
- docs/development/contributing.md
- docs/development/development-setup.md
- .github/CODEOWNERS

### Nice to Have / Later

- docs/comparison.md
- docs/roadmap.md
- docs/advanced/prompt-construction.md
- CITATION.cff
- docs/SUPPORT.md (if needed)
- Video tutorials / external guides (not in-repo)

---

## Notes on Specific Documents

- **for-agents-and-sidecars.md** is unusually important for this project because of its dual positioning (human tool + infrastructure for future sidecars).
- **output-artifacts.md** should be very detailed — this is one of the main value propositions.
- The `development/` section can stay relatively light until there is real external contribution interest.
- We should avoid over-documenting internal recovery-layer specifics in the public docs.

---

**Current Status (as of this proposal):**

- Many of the "Must Have" items above do not exist yet.
- Existing docs (usage-notes.md, dogfooding-case-study.md, examples) are useful but should be restructured into the above layout over time.

This list is intended to be the complete target state so we stop having the "I thought docs were done" conversation.
