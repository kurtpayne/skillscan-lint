"""skillscan-lint — Quality linter for AI agent skill files."""

__version__ = "0.1.0"

from skillscan_lint.linter import lint_directory, lint_file
from skillscan_lint.models import LintFinding, LintResult, ScanSummary, Severity

__all__ = [
    "lint_file",
    "lint_directory",
    "LintFinding",
    "LintResult",
    "ScanSummary",
    "Severity",
]
