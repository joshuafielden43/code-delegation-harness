# Example Usage

This is a concrete, ready-to-use test you can run right now.

## Concrete Test You Can Run Today

**Goal**: Exercise the current harness end-to-end and see the modern outputs (structured JSON + human review report + ready-to-apply patch).

### Target (completely disposable — zero risk)
Use this file that exists only for testing the delegate:

`docs/examples/safe_test_target.py`

It contains three small functions that are not used anywhere.

### Exact task to delegate

```
Add proper Google-style docstrings and type hints to all three functions in docs/examples/safe_test_target.py (calculate_total, format_user_name, and is_valid_email). Do not change any logic or behavior. Only improve documentation and add type hints.
```

### Recommended invocation (copy-paste ready)

Inside your session, after loading the skill:

```
Delegate the following task to Grok using the grok-coding-delegate skill:

Task: Add proper Google-style docstrings and type hints to all three functions in docs/examples/safe_test_target.py (calculate_total, format_user_name, and is_valid_email). Do not change any logic or behavior. Only improve documentation and add type hints.

Target directory: [your current project root, e.g. ~/.grok/worktrees/jcf/scratch]

Use --output-file /tmp/delegate-test-001.json when running the underlying wrapper so you get the full artifacts.
```

### What you will receive (the actual END RESULT artifacts)

When the delegation completes with structured output, you will get three files:

1. `/tmp/delegate-test-001.json` — full machine-readable result
2. `/tmp/delegate-test-001.report.md` — the primary document for review (status, what changed, rich descriptions, diff previews, etc.)
3. `/tmp/delegate-test-001.patch` — a ready-to-apply unified diff you can inspect or apply with `git apply`

Open the `.report.md` first. It is designed as the thing to review when evaluating the actual delivered work.

## Design / API Collaboration Level

If you want to collaborate on the output schema, the shape of the human report, what fields are most useful for you when reviewing end results, or the overall API surface between the delegate and you, that is exactly the right level of involvement. Just describe the direction you want and I can implement against it.

## Safety Notes

- The target file is intentionally throwaway.
- The task is purely additive (docs + types).
- You can run it in the recovery layer worktree with no impact on anything else.