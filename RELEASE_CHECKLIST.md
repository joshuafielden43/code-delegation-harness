# Release Checklist (gcdh)

Use this checklist before cutting any release (patch or minor). It is meant to be used in conjunction with `docs/development/release-process.md`.

## Pre-Release Preparation

- [ ] Working tree is clean (`git status --porcelain` is empty)
- [ ] All tests pass (`python -m pytest tests/ -q`)
- [ ] `CHANGELOG.md` has been updated:
  - Move relevant items from `## Unreleased` into a new `## [X.Y.Z] - YYYY-MM-DD` section
  - Write a clear summary + highlights
- [ ] Version bumped in both places:
  - `pyproject.toml`
  - `src/code_delegation_harness/__init__.py` (fallback `__version__`)
- [ ] Active dogfood prompts are committed and referenced in `references/dogfood-prompts/README.md`
- [ ] `MEETING_OF_MODELS_TRANSCRIPT.md` (single source of truth) is up to date with recent work
- [ ] `RELEASE_CHECKLIST.md` and this document have been reviewed for accuracy
- [ ] Any user-facing docs (README, runbook, usage notes) that need updating for this release have been touched

## Build & Verification

- [ ] Build from a clean checkout:
  ```bash
  python -m pip install --upgrade build
  python -m build --wheel --sdist
  ```
- [ ] Verify the built artifacts exist in `dist/`
- [ ] (Optional but recommended) Test install in a fresh virtual environment:
  ```bash
  python -m venv /tmp/verify-release
  source /tmp/verify-release/bin/activate
  pip install dist/code_delegation_harness-*.whl
  gcdh --version
  gcdh --help
  ```

## Tagging & Publishing

- [ ] Create annotated tag:
  ```bash
  git tag -a vX.Y.Z -m "vX.Y.Z - Short title

  - Highlight 1
  - Highlight 2"
  ```
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Upload to PyPI (after TestPyPI if this is the first time for this version series):
  ```bash
  python -m pip install --upgrade twine
  twine upload dist/*
  ```
- [ ] Create GitHub Release:
  - Use the tag just pushed
  - Title: `vX.Y.Z - Short title`
  - Paste the relevant CHANGELOG section into the release notes
- [ ] Verify on PyPI: https://pypi.org/project/code-delegation-harness/X.Y.Z/

## Post-Release

- [ ] Confirm the new version appears correctly on GitHub releases and PyPI
- [ ] Update any internal references if needed (rare)
- [ ] Announce in the Dialogue (if relevant to current dogfood partners)
- [ ] Celebrate responsibly

## Quick Sanity Commands

```bash
# Clean check
git status --porcelain

# Test everything
python -m pytest tests/ -q

# Current version (from source)
python -c "from code_delegation_harness import __version__; print(__version__)"
```

## Notes for Future Releases

- Dogfood prompts and the transcript are now treated as first-class release artifacts. Make sure they are in good shape.
- The nuc-style micro-pass + apply pattern has proven valuable for controlled, high-signal work. Consider whether any new release notes should mention improved support for this style of dogfooding.
- Keep this checklist short and actionable. If a step becomes complex, move the detail into `release-process.md` and just link here.