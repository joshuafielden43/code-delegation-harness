#!/usr/bin/env python3
"""
Compatibility shim.

The real implementation lives in src/code_delegation_harness/harness.py.
This is a legacy compatibility shim for older invocation patterns.

This file exists so that direct execution from the repo
(`python scripts/grok_delegate.py ...`) continues to work without changes.
"""
import sys
from pathlib import Path

# Add the src directory so we can import the real code
repo_root = Path(__file__).parent.parent
src_dir = repo_root / "src"
sys.path.insert(0, str(src_dir))

from code_delegation_harness import main

if __name__ == "__main__":
    main()
