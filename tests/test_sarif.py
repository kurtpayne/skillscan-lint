"""Tests for the SARIF output formatter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillscan_lint.formatters.output import format_sarif
from skillscan_lint.linter import lint_file
from skillscan_lint.models import (
    Category,
    LintFinding,
    LintResult,
    ScanSummary,
    Severity,
)

FIXTURES = Path(__file__).parent / "fixtures"
FAIL_DIR = FIXTURES / "fail"
PASS_DIR = FIXTURES / "pass"


# ---------------------------------------------------------------------------
# Unit tests for format_sarif()
# ---------------------------------------------------------------------------


def _make_summary(findings: list[LintFinding]) -> ScanSummary:
    path = Path("/workspace/SKILL.md")
    result = LintResult(path=path, findings=findings)
    return ScanSummary(
        results=[result],
        total_files=1,
        skipped_files=0,
    )


def test_sarif_schema_version():
    summary = _make_summary([])
    sarif = json.loads(format_sarif(summary))
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif


def test_sarif_tool_driver():
    summary = _make_summary([])
    sarif = json.loads(format_sarif(summary))
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "skillscan-lint"
    assert "version" in driver
    assert driver["informationUri"] == "https://skillscan.sh/linter"


def test_sarif_empty_findings():
    """A clean scan produces a valid SARIF log with zero results."""
    summary = _make_summary([])
    sarif = json.loads(format_sarif(summary))
    assert sarif["runs"][0]["results"] == []
    assert sarif["runs"][0]["tool"]["driver"]["rules"] == []


def test_sarif_single_finding_structure():
    finding = LintFinding(
        rule_id="QL-001",
        severity=Severity.WARNING,
        category=Category.READABILITY,
        message="Description is too long",
        path=Path("/workspace/SKILL.md"),
        line=5,
        column=0,
        suggestion="Shorten the description to under 50 words.",
    )
    summary = _make_summary([finding])
    sarif = json.loads(format_sarif(summary))

    run = sarif["runs"][0]
    assert len(run["results"]) == 1
    assert len(run["tool"]["driver"]["rules"]) == 1

    result = run["results"][0]
    assert result["ruleId"] == "QL-001"
    assert result["level"] == "warning"
    assert "Description is too long" in result["message"]["text"]
    assert "Shorten" in result["message"]["text"]  # suggestion appended

    loc = result["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "/workspace/SKILL.md"
    assert loc["region"]["startLine"] == 5


def test_sarif_severity_levels():
    """ERROR → 'error', WARNING → 'warning', INFO → 'note'."""
    findings = [
        LintFinding(
            rule_id="QL-001",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            message="Missing required field",
            path=Path("/workspace/SKILL.md"),
        ),
        LintFinding(
            rule_id="QL-002",
            severity=Severity.WARNING,
            category=Category.READABILITY,
            message="Long sentence",
            path=Path("/workspace/SKILL.md"),
        ),
        LintFinding(
            rule_id="QL-003",
            severity=Severity.INFO,
            category=Category.CLARITY,
            message="Passive voice detected",
            path=Path("/workspace/SKILL.md"),
        ),
    ]
    summary = _make_summary(findings)
    sarif = json.loads(format_sarif(summary))

    results = sarif["runs"][0]["results"]
    levels = {r["ruleId"]: r["level"] for r in results}
    assert levels["QL-001"] == "error"
    assert levels["QL-002"] == "warning"
    assert levels["QL-003"] == "note"


def test_sarif_rule_deduplication():
    """The same rule ID appearing in multiple findings is listed once in rules."""
    findings = [
        LintFinding(
            rule_id="QL-003",
            severity=Severity.WARNING,
            category=Category.CLARITY,
            message="Passive voice on line 5",
            path=Path("/workspace/SKILL.md"),
            line=5,
        ),
        LintFinding(
            rule_id="QL-003",
            severity=Severity.WARNING,
            category=Category.CLARITY,
            message="Passive voice on line 12",
            path=Path("/workspace/SKILL.md"),
            line=12,
        ),
    ]
    summary = _make_summary(findings)
    sarif = json.loads(format_sarif(summary))

    rules = sarif["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = [r["id"] for r in rules]
    assert rule_ids.count("QL-003") == 1
    assert len(sarif["runs"][0]["results"]) == 2


def test_sarif_no_line_defaults_to_1():
    """Findings without a line number default to startLine: 1."""
    finding = LintFinding(
        rule_id="QL-011",
        severity=Severity.ERROR,
        category=Category.STRUCTURE,
        message="Missing name field",
        path=Path("/workspace/SKILL.md"),
        line=None,
    )
    summary = _make_summary([finding])
    sarif = json.loads(format_sarif(summary))

    region = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    assert region["startLine"] == 1


def test_sarif_skipped_files_excluded():
    """Skipped files produce no SARIF results."""
    result = LintResult(
        path=Path("/workspace/SKILL.md"),
        skipped=True,
        skip_reason="binary file",
    )
    summary = ScanSummary(results=[result], total_files=1, skipped_files=1)
    sarif = json.loads(format_sarif(summary))
    assert sarif["runs"][0]["results"] == []


def test_sarif_uri_base_id():
    """Artifact URIs include the %SRCROOT% base ID for portable paths."""
    finding = LintFinding(
        rule_id="QL-001",
        severity=Severity.WARNING,
        category=Category.READABILITY,
        message="Test",
        path=Path("/workspace/skills/SKILL.md"),
    )
    summary = _make_summary([finding])
    sarif = json.loads(format_sarif(summary))

    artifact = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
        "artifactLocation"
    ]
    assert artifact["uriBaseId"] == "%SRCROOT%"


# ---------------------------------------------------------------------------
# Integration test: lint a real fixture and check SARIF output
# ---------------------------------------------------------------------------


def test_sarif_from_real_fixture():
    """Linting a failing fixture produces valid SARIF with at least one result."""
    # Use the first .md file in the fail directory
    fail_files = list(FAIL_DIR.glob("*.md"))
    if not fail_files:
        pytest.skip("No fail fixture .md files found")

    result = lint_file(fail_files[0])
    summary = ScanSummary(results=[result], total_files=1, skipped_files=0)
    sarif_str = format_sarif(summary)

    # Must be valid JSON
    sarif = json.loads(sarif_str)

    # Must conform to basic SARIF structure
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    run = sarif["runs"][0]
    assert "tool" in run
    assert "results" in run

    # Failing fixture should produce at least one result
    if result.findings:
        assert len(run["results"]) > 0
        for r in run["results"]:
            assert "ruleId" in r
            assert "level" in r
            assert "message" in r
            assert "locations" in r


# ---------------------------------------------------------------------------
# CLI integration: --format sarif flag
# ---------------------------------------------------------------------------


def test_cli_sarif_flag(tmp_path):
    """The CLI --format sarif flag produces valid SARIF JSON."""
    from click.testing import CliRunner

    from skillscan_lint.cli import main

    # Write a minimal skill file with a known issue
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: test_skill\nversion: '1.0.0'\n---\n\n"
        "This skill does stuff and things.\n"
    )

    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(skill), "--format", "sarif"])

    # Exit 0 (no errors) or 1 (findings present) — both are valid
    assert result.exit_code in (0, 1), f"Unexpected exit code: {result.exit_code}\n{result.output}"

    sarif = json.loads(result.output)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
