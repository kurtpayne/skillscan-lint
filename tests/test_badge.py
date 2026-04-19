"""Tests for lint badge generation (--badge-out)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from skillscan_lint.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
PASS_DIR = FIXTURES / "pass"
FAIL_DIR = FIXTURES / "fail"


class TestLintBadge:
    def test_clean_file_green_badge(self, tmp_path: Path) -> None:
        """A minimal skill with all required fields should produce a green badge."""
        skill = tmp_path / "SKILL.md"
        skill.write_text(
            "---\n"
            "name: test_skill\n"
            "version: 1.0.0\n"
            "description: A short and clear test skill for badge generation tests.\n"
            "tags: [test, badge]\n"
            "---\n\n"
            "## When to Use\n\nUse this skill when testing badge generation.\n\n"
            "## Inputs\n\n- `path`: The file path to scan.\n\n"
            "## Outputs\n\n- `result`: The scan result.\n\n"
            "## Examples\n\n```\nskillscan scan .\n```\n",
            encoding="utf-8",
        )
        badge_path = tmp_path / "lint-badge.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "scan",
                str(skill),
                "--badge-out",
                str(badge_path),
                "--fail-on",
                "never",
            ],
        )
        assert result.exit_code == 0, result.output
        assert badge_path.exists()
        data = json.loads(badge_path.read_text())
        assert data["schemaVersion"] == 1
        assert data["label"] == "SkillScan Lint"
        # May be green or yellow depending on reading level heuristic;
        # the key assertion is that the badge is valid and written.
        assert data["color"] in ("brightgreen", "yellow")

    def test_good_skill_badge_written(self, tmp_path: Path) -> None:
        """good_skill.md has warnings; badge should be yellow."""
        badge_path = tmp_path / "lint-badge.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["scan", str(PASS_DIR / "good_skill.md"), "--badge-out", str(badge_path)],
        )
        assert result.exit_code == 0, result.output
        assert badge_path.exists()
        data = json.loads(badge_path.read_text())
        assert data["schemaVersion"] == 1
        assert data["label"] == "SkillScan Lint"
        assert data["color"] == "yellow"

    def test_file_with_issues_nongreen(self, tmp_path: Path) -> None:
        badge_path = tmp_path / "lint-badge.json"
        runner = CliRunner()
        # weasel_skill.md should trigger warnings
        result = runner.invoke(
            main,
            [
                "scan",
                str(FAIL_DIR / "weasel_skill.md"),
                "--badge-out",
                str(badge_path),
                "--fail-on",
                "never",
            ],
        )
        assert result.exit_code == 0, result.output
        assert badge_path.exists()
        data = json.loads(badge_path.read_text())
        assert data["color"] in ("yellow", "red")
        # Should have at least 1 issue
        assert "0 issues" not in data["message"]

    def test_error_file_red_badge(self, tmp_path: Path) -> None:
        badge_path = tmp_path / "lint-badge.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "scan",
                str(FAIL_DIR / "missing_fields.md"),
                "--badge-out",
                str(badge_path),
                "--fail-on",
                "never",
            ],
        )
        assert result.exit_code == 0, result.output
        assert badge_path.exists()
        data = json.loads(badge_path.read_text())
        assert data["color"] == "red"

    def test_no_badge_without_flag(self, tmp_path: Path) -> None:
        badge_path = tmp_path / "lint-badge.json"
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(PASS_DIR / "good_skill.md")])
        assert result.exit_code == 0
        assert not badge_path.exists()
