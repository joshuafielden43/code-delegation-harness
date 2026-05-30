---
title: Dogfooding Case Study — The Grok Coding Delegate Built Its Own Night Batcher
type: case-study
tags: [dogfooding, delegation, meta, 8gb-mac, sidecar]
created: 2026-05-29
---

# Dogfooding Case Study

**The Grok Coding Delegate was used to implement the production version of the night batcher that protects the 8 GB Mac during the exact sidecar work that inspired the harness in the first place.**

Full narrative story (sanitized public version recommended for sharing):

[[Grok-Honey/Notes/Dogfooding-the-Grok-Coding-Delegate]]

## Key Facts

- **Problem domain**: 8 GB Mac + heavy YouTube operator corpus sidecar + desire to move lightweight first-pass cleaning (ad reads, filler, tags) onto the Mac at night only.
- **Constraint**: The batcher must never kill processes (ComfyUI or OpenWhispr) if a human is actively using the machine.
- **User permission**: Explicit authorization was given to kill ComfyUI for this job.
- **Implementation vehicle**: The `grok-coding-delegate` harness itself.
- **Outcome**: The cleaner now contains a proper macOS `HIDIdleTime` idle checker, safe kill functions, `--night-batch` discipline, and full integration with the two-pass architecture.

This is a strong early demonstration that the harness removes round-trip tax while producing production-grade, safety-conscious code on a specific Low-memory Mac (specific daily driver details given once in the story) and a modest NUC.

Per the user's direction, the full authentic collaboration record (including the private Dialogue between the AIs) is to be preserved in the vault for the duration of the project. Only a sanitized version of this story is intended for any external sharing.

## Artifacts

- Production cleaner: `~/.grok/worktrees/jcf/scratch/scripts/honeyneo_transcript_cleaner.py` (and live mirror)
- Story document: `Grok-Honey/Notes/Dogfooding-the-Grok-Coding-Delegate.md` (sanitized version)

---

## Later Demonstrated Value (Long-Running / Background Resilience)

Real use of the harness on the Vault-Tag-Normalizer task (77 normalization decisions across 82 files) directly exposed the 300s inner timeout + background restart pattern. This drove the subsequent investment in:
- Persistent rich `.grok-delegate-run-*.status` files with full launch/wait/complete lifecycle
- `--status`, smart `--resume`, and reliable final artifact delivery (`.report.md` + `.patch`) even after background phases

The harness is now significantly more suitable for the multi-hour vault-scale work that the sidecar architecture will eventually need to support.

*Part of an AI tooling and delegation experiment.*