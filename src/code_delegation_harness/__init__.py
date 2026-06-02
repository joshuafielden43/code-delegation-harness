"""
Code Delegation Harness

Professional packaging for the `gcdh` command.
"""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

from .harness import (
    main,
    prune_completed_status_files,
    normalize_result,
    render_human_report,
    RetryPolicy,
    load_checkpoint_context,
    _determine_status,
    _compute_diffs_and_stats,
    _print_dry_run_preview,
    _write_status_file,
    _finalize_delegate_status,
    _wait_for_background_completion,
)

from .status import StatusManager, register_crash_protection

try:
    __version__ = _pkg_version("code-delegation-harness")
except (PackageNotFoundError, Exception):
    __version__ = "0.3.1"

__all__ = [
    "main",
    "prune_completed_status_files",
    "normalize_result",
    "render_human_report",
    "RetryPolicy",
    "load_checkpoint_context",
    "register_crash_protection",
    "__version__",
    "StatusManager",
]
