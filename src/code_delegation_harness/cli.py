"""
CLI entry point for the `gcdh` command.

This module provides the console_script target:
    gcdh = "code_delegation_harness.cli:main"
"""
from .harness import main

__all__ = ["main"]
