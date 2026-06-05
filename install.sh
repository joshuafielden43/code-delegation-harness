#!/usr/bin/env bash
# install.sh — reinstall gcdh from this repo into the system Python 3.9 user env.
#
# Run this whenever:
#   - the repo has moved
#   - a new checkout / worktree is created
#   - gcdh gives ModuleNotFoundError
#   - you've pulled new code and want the installed binary to reflect it
#
# What it does:
#   1. Finds the same Python 3.9 that the installed gcdh shebang uses
#   2. pip install -e . from this repo root (editable, so changes take effect immediately)
#   3. Verifies the install with --version
#
# Usage:
#   ./install.sh
#   ./install.sh --with-intake    # also installs anthropic SDK for intake gate

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Library/Developer/CommandLineTools/usr/bin/python3"

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: expected Python at $PYTHON — adjust PYTHON= in this script if your CLT path differs." >&2
  exit 1
fi

EXTRAS=""
if [[ "${1:-}" == "--with-intake" ]]; then
  EXTRAS="[intake]"
  echo "Installing with [intake] extras (Anthropic SDK)..."
fi

echo "Installing code-delegation-harness from $REPO_DIR ..."
"$PYTHON" -m pip install -e "${REPO_DIR}${EXTRAS}" --quiet

echo ""
echo "Verifying:"
gcdh --version
echo ""
echo "Install path:"
"$PYTHON" -c "import code_delegation_harness; print('  ', code_delegation_harness.__file__)"
echo ""
echo "Done. gcdh is ready."
