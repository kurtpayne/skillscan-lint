"""Core linter engine for skillscan-lint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Ensure all rules are registered by importing the module
import skillscan_lint.rules.quality  # noqa: F401
from skillscan_lint.detectors.graph import analyze_graph
from skillscan_lint.models import LintFinding, LintResult, ScanSummary
from skillscan_lint.parser import ParseError, is_skill_file, parse_skill_file
from skillscan_lint.rules.base import get_all_rules


def lint_file(
    path: Path,
    rules: list | None = None,
    skip_ids: set[str] | None = None,
) -> LintResult:
    """Lint a single skill file and return a LintResult."""
    if rules is None:
        rules = get_all_rules()
    if skip_ids is None:
        skip_ids = set()

    try:
        content, parsed = parse_skill_file(path)
    except ParseError as e:
        result = LintResult(path=path, skipped=True, skip_reason=str(e))
        return result

    findings: list[LintFinding] = []
    for rule in rules:
        if rule.rule_id in skip_ids:
            continue
        try:
            rule_findings = rule.check(path, content, parsed)
            findings.extend(rule_findings)
        except Exception:  # noqa: BLE001
            # Rule errors should never crash the linter
            pass

    return LintResult(path=path, findings=findings)


def lint_directory(
    root: Path,
    recursive: bool = True,
    skip_ids: set[str] | None = None,
    include_graph: bool = True,
) -> ScanSummary:
    """Lint all skill files under a directory."""
    if skip_ids is None:
        skip_ids = set()

    rules = get_all_rules()
    skill_paths = _collect_skill_files(root, recursive)

    results: list[LintResult] = []
    parsed_skills: list[tuple[Path, str, dict[str, Any]]] = []
    skipped = 0

    for path in skill_paths:
        result = lint_file(path, rules=rules, skip_ids=skip_ids)
        results.append(result)
        if result.skipped:
            skipped += 1
        else:
            try:
                content, parsed = parse_skill_file(path)
                parsed_skills.append((path, content, parsed))
            except ParseError:
                pass

    # Graph analysis runs across all files at once (even single files for dangling ref checks)
    if include_graph and len(parsed_skills) >= 1:
        graph_findings = analyze_graph(parsed_skills)
        # Attach graph findings to the appropriate result, or create a synthetic one
        _path_to_result = {r.path: r for r in results}
        for finding in graph_findings:
            if finding.path in _path_to_result:
                _path_to_result[finding.path].findings.append(finding)
            else:
                # Graph finding for an unknown path — attach to a synthetic result
                synthetic = LintResult(path=finding.path, findings=[finding])
                results.append(synthetic)

    return ScanSummary(
        results=results,
        total_files=len(skill_paths),
        skipped_files=skipped,
    )


def _collect_skill_files(root: Path, recursive: bool) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root] if is_skill_file(root) else []

    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in root.glob(pattern)
        if p.is_file() and is_skill_file(p)
    )
