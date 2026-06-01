# Release Process

This document describes how to cut and publish releases of the Code Delegation Harness.

## Overview

Releases are published to both GitHub and PyPI.

- GitHub Releases provide the tagged source and release notes.
- PyPI provides the installable package via `pip install code-delegation-harness`.

## Prerequisites

- You have write access to the GitHub repository.
- You have a PyPI account with maintainer rights on the `code-delegation-harness` project (or use GitHub Trusted Publishing).
- The `build` and `twine` packages installed in your publishing environment.

## Step-by-Step Release Process

### 1. Prepare the Release

- Ensure `main` is up to date and all desired changes are merged.
- Update the version in `pyproject.toml` (e.g., from `0.2.1` to `0.2.2` or `0.3.0`).
- Update `CHANGELOG.md`:
  - Move relevant items from `[Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section.
  - Add highlights, breaking changes, and migration notes if applicable.
- Review and update `README.md` and other docs if the release includes user-facing changes.
- Commit these changes with a message like `Prepare v0.2.2 release`.

### 2. Build the Distributions

From the root of the repository:

```bash
python -m pip install --upgrade build
python -m build --wheel --sdist
```

This will create files in `dist/`:
- `code_delegation_harness-X.Y.Z-py3-none-any.whl`
- `code_delegation_harness-X.Y.Z.tar.gz`

**Important**: Always build from a clean checkout on the correct branch/tag.

### 3. Create and Push the Git Tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z - Brief release title

- Key change 1
- Key change 2"
git push origin vX.Y.Z
```

This creates the GitHub release tag.

### 4. Upload to PyPI

#### Option A: Using API Token (Current Method)

```bash
python -m pip install --upgrade twine
twine upload dist/*
```

When prompted:
- Username: `__token__`
- Password: Your PyPI API token (starts with `pypi-`)

#### Option B: GitHub Trusted Publishing (Recommended for Future)

See the section below for setting this up. Once configured, uploads can be triggered from GitHub Actions without storing long-lived tokens.

### 5. Create the GitHub Release

Go to: https://github.com/joshuafielden43/code-delegation-harness/releases/new

- Select the tag you just pushed.
- Title: `vX.Y.Z - Release Title`
- Copy the relevant section from `CHANGELOG.md` into the release notes.
- Publish the release.

### 6. Verify

- Check PyPI: https://pypi.org/project/code-delegation-harness/X.Y.Z/
- Test installation in a fresh environment:
  ```bash
  pip install code-delegation-harness==X.Y.Z
  gcdh --version
  ```

## Lessons from the First Public Release (v0.2.1)

- **Always use TestPyPI first** for the initial uploads of a project. Real PyPI uploads are permanent and version numbers cannot be reused.
- Environment confusion is common. The person publishing should use a dedicated, clean virtual environment (not their daily driver or agent environment) to avoid picking up the wrong Python or packages.
- Git-based installs (`pip install git+...`) are **not** ideal for primary agents. They pull full history and cause issues in constrained environments. Push for proper PyPI releases as the default.
- The first release involved significant last-minute documentation work and README grounding. Plan buffer time for this in future releases.
- PRs created for testing the contribution flow (e.g., PR #1 and PR #2) were useful but highlighted that real work should eventually flow through the harness itself for dogfooding.

## Companion Documents

- `RELEASE_CHECKLIST.md` (repo root) — Practical, actionable checklist to use before every release.
- `references/dogfood-prompts/README.md` — Current state and organization of active dogfood prompts.

## Future Improvements

- Set up GitHub Actions + Trusted Publishing for automated releases (no manual token handling).
- Add automated changelog generation or release drafting.
- Consider a `make release` target or more robust `scripts/release.sh`.

## Trusted Publishing (Recommended Future Setup)

GitHub Trusted Publishing allows publishing to PyPI without storing API tokens.

Steps (high level):
1. On PyPI, go to the project settings for `code-delegation-harness` → "Publishing" → "Add a trusted publisher".
2. Select GitHub and provide the repository, workflow filename, and environment (optional).
3. Create a matching GitHub Actions workflow that builds and calls the PyPI publish action on tag push.
4. Future releases can be triggered by pushing a tag, with GitHub handling the authentication.

This eliminates the need for manual `twine upload` with tokens.

## Contact

For questions about the release process, reach out in the internal dialogue or open an issue on the repository.
