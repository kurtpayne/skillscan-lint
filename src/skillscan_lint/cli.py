"""CLI entry point for skillscan-lint."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from skillscan_lint.formatters.output import format_compact, format_json, print_rich
from skillscan_lint.linter import lint_directory
from skillscan_lint.models import ScanSummary


@click.group()
@click.version_option(package_name="skillscan-lint")
def main() -> None:
    """skillscan-lint — Quality linter for AI agent skill files."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "compact", "json"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--no-recursive",
    is_flag=True,
    default=False,
    help="Do not recurse into subdirectories.",
)
@click.option(
    "--no-graph",
    is_flag=True,
    default=False,
    help="Skip skill invocation graph analysis.",
)
@click.option(
    "--skip",
    "skip_ids",
    multiple=True,
    metavar="RULE_ID",
    help="Rule IDs to skip (repeatable). E.g. --skip QL-003 --skip QL-005",
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning", "never"]),
    default="error",
    show_default=True,
    help="Exit with non-zero code when findings at this severity or above are found.",
)
def scan_cmd(
    path: Path,
    output_format: str,
    no_recursive: bool,
    no_graph: bool,
    skip_ids: tuple[str, ...],
    fail_on: str,
) -> None:
    """Scan a skill file or directory for quality issues."""
    skip_set = set(skip_ids)

    if path.is_file():
        from skillscan_lint.linter import lint_file
        result = lint_file(path, skip_ids=skip_set)
        summary = ScanSummary(
            results=[result],
            total_files=1,
            skipped_files=1 if result.skipped else 0,
        )
    else:
        summary = lint_directory(
            path,
            recursive=not no_recursive,
            skip_ids=skip_set,
            include_graph=not no_graph,
        )

    if output_format == "json":
        click.echo(format_json(summary))
    elif output_format == "compact":
        click.echo(format_compact(summary))
    else:
        print_rich(summary)

    # Exit code logic
    if fail_on == "never":
        sys.exit(0)
    elif fail_on == "error" and not summary.passed:
        sys.exit(1)
    elif fail_on == "warning" and (summary.total_errors > 0 or summary.total_warnings > 0):
        sys.exit(1)
    else:
        sys.exit(0)


@main.command("rules")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def rules_cmd(output_format: str) -> None:
    """List all available lint rules."""
    import json as _json

    from skillscan_lint.rules.base import get_all_rules

    rules = sorted(get_all_rules(), key=lambda r: r.rule_id)

    if output_format == "json":
        data = [
            {
                "id": r.rule_id,
                "severity": r.severity.value,
                "category": r.category.value,
                "description": r.description,
            }
            for r in rules
        ]
        click.echo(_json.dumps(data, indent=2))
        return

    try:
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Severity", no_wrap=True)
        table.add_column("Category", no_wrap=True)
        table.add_column("Description")

        SEV_COLORS = {"error": "red", "warning": "yellow", "info": "cyan"}
        for r in rules:
            color = SEV_COLORS.get(r.severity.value, "white")
            table.add_row(
                r.rule_id,
                f"[{color}]{r.severity.value}[/{color}]",
                r.category.value,
                r.description,
            )
        console.print(table)
    except ImportError:
        # Fallback plain text
        for r in rules:
            click.echo(f"{r.rule_id}\t{r.severity.value}\t{r.category.value}\t{r.description}")
