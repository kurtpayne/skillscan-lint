"""Output formatters for skillscan-lint."""

from __future__ import annotations

import json
from typing import cast

from skillscan_lint.models import ScanSummary, Severity

try:
    from rich.console import Console
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def format_compact(summary: ScanSummary) -> str:
    """One line per finding, similar to eslint compact output."""
    lines = []
    for result in summary.results:
        if result.skipped:
            lines.append(f"SKIP {result.path}: {result.skip_reason}")
            continue
        for f in result.findings:
            loc = f":{f.line}" if f.line else ""
            lines.append(
                f"{f.severity.value.upper()} {f.path}{loc} [{f.rule_id}] {f.message}"
            )
    lines.append("")
    lines.append(
        f"{'PASS' if summary.passed else 'FAIL'} — "
        f"{summary.total_files} files, "
        f"{summary.total_errors} errors, "
        f"{summary.total_warnings} warnings"
    )
    return "\n".join(lines)


def format_json(summary: ScanSummary) -> str:
    """JSON output for CI integration."""
    output: dict[str, object] = {
        "passed": summary.passed,
        "total_files": summary.total_files,
        "skipped_files": summary.skipped_files,
        "total_errors": summary.total_errors,
        "total_warnings": summary.total_warnings,
        "results": [],
    }
    results: list[dict[str, object]] = cast(list, output["results"])
    for result in summary.results:
        findings: list[dict[str, object]] = []
        for f in result.findings:
            findings.append({
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "category": f.category.value,
                "message": f.message,
                "line": f.line,
                "suggestion": f.suggestion,
            })
        results.append({
            "path": str(result.path),
            "passed": result.passed,
            "skipped": result.skipped,
            "findings": findings,
        })
    return json.dumps(output, indent=2)


def print_rich(summary: ScanSummary, console: Console | None = None) -> None:
    """Rich terminal output with color and tables."""
    if not HAS_RICH:
        print(format_compact(summary))
        return

    if console is None:
        console = Console()

    SEVERITY_COLORS = {
        Severity.ERROR: "bold red",
        Severity.WARNING: "yellow",
        Severity.INFO: "cyan",
    }

    for result in summary.results:
        if result.skipped:
            console.print(f"[dim]SKIP[/dim] {result.path}: {result.skip_reason}")
            continue
        if not result.findings:
            console.print(f"[green]✓[/green] {result.path}")
            continue

        console.print(f"\n[bold]{result.path}[/bold]")
        for f in result.findings:
            color = SEVERITY_COLORS.get(f.severity, "white")
            loc = f":{f.line}" if f.line else ""
            console.print(
                f"  [{color}]{f.severity.value.upper()}[/{color}] "
                f"[dim]{f.rule_id}[/dim]{loc} {f.message}"
            )
            if f.suggestion:
                console.print(f"  [dim]  → {f.suggestion}[/dim]")

    # Summary bar
    console.print()
    if summary.passed:
        console.print(
            f"[bold green]✓ PASS[/bold green] — "
            f"{summary.total_files} files scanned, "
            f"{summary.total_warnings} warnings"
        )
    else:
        console.print(
            f"[bold red]✗ FAIL[/bold red] — "
            f"{summary.total_files} files scanned, "
            f"[red]{summary.total_errors} errors[/red], "
            f"{summary.total_warnings} warnings"
        )
