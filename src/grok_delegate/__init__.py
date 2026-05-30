"""
Grok Coding Delegate

Professional packaging for the `gcdh` command.
"""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

from .harness import (
    main,
    prune_completed_status_files,
    normalize_result,
    render_human_report,
    _determine_status,
    _compute_diffs_and_stats,
    _print_dry_run_preview,
    _make_delegate_status,
    _write_status_file,
    _finalize_delegate_status,
    _wait_for_background_completion,
)

try:
    __version__ = _pkg_version("grok-coding-delegate")
except (PackageNotFoundError, Exception):
    __version__ = "0.2.0"

__all__ = [
    "main",
    "prune_completed_status_files",
    "normalize_result",
    "render_human_report",
    "__version__",
]
