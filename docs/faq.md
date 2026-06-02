# Frequently Asked Questions

## General

**What is the Code Delegation Harness?**

A professional CLI tool for delegating coding tasks to LLMs (primarily Grok, but designed to be model-agnostic) while producing high-quality, reviewable artifacts.

**Why not just use the normal Grok interface?**

The harness gives you:
- Structured output (JSON + human report + patch)
- Strong working directory controls
- Long-running / background support
- Clean separation between your primary agent and the delegated work

## Usage

**Can I use this with models other than Grok?**

The architecture supports it (the backend is driven by the `--model` flag), but the current implementation calls the `grok` CLI. Other backends would require additional adapter work.

**Does it work with agents and sidecars?**

Yes. This is one of the primary design goals. See [For Agents and Sidecars](usage/for-agents-and-sidecars.md).

**What happens if the inner run times out?**

By default it fails. With `--wait-for-completion` it will keep polling in the background until the task finishes or `--max-wait` is exceeded.

## Output & Artifacts

**What exactly is in the output JSON?**

See [Output Artifacts](usage/output-artifacts.md) for the full schema.

**Can I apply the generated patch automatically?**

You can, but we strongly recommend human review first. The `.patch` file is provided for convenience, not as a "just apply it" button.

## Development & Contribution

**Can I use the harness to work on the harness itself?**

Yes. We dogfood it heavily.

**How do I report bugs or request features?**

See [CONTRIBUTING.md](../CONTRIBUTING.md) and open an issue with the appropriate template.
