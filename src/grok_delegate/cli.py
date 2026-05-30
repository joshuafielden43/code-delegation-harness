"""
CLI entry point for the `gcdh` command.

This module provides the console_script target:
    gcdh = "grok_delegate.cli:main"
"""
from .harness import main

__all__ = ["main"]
