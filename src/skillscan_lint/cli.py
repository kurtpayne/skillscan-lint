"""CLI entry point for skillscan-lint."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from skillscan_lint.config import LintConfig, load_config
from skillscan_lint.formatters.output import format_compact, format_json, format_sarif, print_rich
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
    type=click.Choice(["rich", "compact", "json", "sarif"]),
    default=None,
    show_default=False,
    help="Output format (default: from config or 'rich').",
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
    default=None,
    show_default=False,
    help="Exit with non-zero code when findings at this severity or above are found (default: from config or 'error').",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to a .skillscan-lint.toml config file.",
)
def scan_cmd(
    path: Path,
    output_format: str | None,
    no_recursive: bool,
    no_graph: bool,
    skip_ids: tuple[str, ...],
    fail_on: str | None,
    config_path: Path | None,
) -> None:
    """Scan a skill file or directory for quality issues."""
    # Load config (explicit path > auto-discovery > defaults)
    cfg: LintConfig = load_config(explicit_path=config_path, search_from=path)

    # CLI flags override config defaults
    effective_format = output_format or cfg.output.format
    effective_fail_on = fail_on or cfg.output.fail_on
    include_graph = not no_graph and not cfg.graph.skip_graph

    # Merge skip sets: CLI --skip flags + config [rules].disable
    skip_set = set(skip_ids) | set(cfg.rules.disable)

    if path.is_file():
        from skillscan_lint.linter import lint_file
        result = lint_file(
            path,
            skip_ids=skip_set,
            severity_overrides=cfg.rules.overrides,
            thresholds=cfg.thresholds,
        )
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
            include_graph=include_graph,
            severity_overrides=cfg.rules.overrides,
            thresholds=cfg.thresholds,
        )

    if effective_format == "json":
        click.echo(format_json(summary))
    elif effective_format == "compact":
        click.echo(format_compact(summary))
    elif effective_format == "sarif":
        click.echo(format_sarif(summary))
    else:
        print_rich(summary)

    # Exit code logic
    if effective_fail_on == "never":
        sys.exit(0)
    elif effective_fail_on == "error" and not summary.passed:
        sys.exit(1)
    elif effective_fail_on == "warning" and (
        summary.total_errors > 0 or summary.total_warnings > 0
    ):
        sys.exit(1)
    else:
        sys.exit(0)


@main.command("config")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to a .skillscan-lint.toml config file.",
)
def config_cmd(config_path: Path | None) -> None:
    """Show the resolved configuration (useful for debugging)."""
    import json as _json

    cfg = load_config(explicit_path=config_path)
    data = {
        "source": str(cfg.source) if cfg.source else None,
        "rules": {
            "disable": cfg.rules.disable,
            "overrides": cfg.rules.overrides,
        },
        "thresholds": {
            "max_description_words": cfg.thresholds.max_description_words,
            "min_description_words": cfg.thresholds.min_description_words,
            "max_sentence_length": cfg.thresholds.max_sentence_length,
        },
        "graph": {
            "skip_graph": cfg.graph.skip_graph,
        },
        "output": {
            "format": cfg.output.format,
            "fail_on": cfg.output.fail_on,
        },
    }
    click.echo(_json.dumps(data, indent=2))


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
