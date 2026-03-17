"""Tests for skillscan-lint rules."""

from __future__ import annotations

from pathlib import Path

from skillscan_lint.linter import lint_file
from skillscan_lint.models import Severity
from skillscan_lint.parser import parse_skill_file
from skillscan_lint.rules.base import get_all_rules, get_rule

FIXTURES = Path(__file__).parent / "fixtures"
PASS_DIR = FIXTURES / "pass"
FAIL_DIR = FIXTURES / "fail"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_parse_markdown_with_frontmatter():
    path = PASS_DIR / "good_skill.md"
    content, parsed = parse_skill_file(path)
    assert parsed["name"] == "fetch_weather"
    assert parsed["version"] == "1.0.0"
    assert "OpenWeatherMap" in parsed["description"]
    assert "_body" in parsed


def test_parse_markdown_no_frontmatter(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("# Just a plain markdown file\n\nNo front-matter here.")
    content, parsed = parse_skill_file(p)
    assert parsed.get("name") is None
    assert "plain markdown" in parsed["_body"]


def test_parse_yaml(tmp_path):
    p = tmp_path / "skill.yaml"
    p.write_text("name: my_skill\ndescription: A test skill.\nversion: '1.0.0'\n")
    content, parsed = parse_skill_file(p)
    assert parsed["name"] == "my_skill"


# ---------------------------------------------------------------------------
# Rule registry tests
# ---------------------------------------------------------------------------

def test_all_rules_registered():
    rules = get_all_rules()
    assert len(rules) >= 15, "Expected at least 15 rules to be registered"


def test_rule_ids_unique():
    rules = get_all_rules()
    ids = [r.rule_id for r in rules]
    assert len(ids) == len(set(ids)), "Duplicate rule IDs detected"


def test_get_rule_by_id():
    rule = get_rule("QL-001")
    assert rule is not None
    assert rule.rule_id == "QL-001"


def test_get_nonexistent_rule():
    assert get_rule("XX-999") is None


# ---------------------------------------------------------------------------
# Good skill — should produce no errors
# ---------------------------------------------------------------------------

def test_good_skill_no_errors():
    result = lint_file(PASS_DIR / "good_skill.md")
    assert result.passed, f"Expected no errors, got: {result.errors}"


# ---------------------------------------------------------------------------
# QL-011 / QL-012 — Missing required fields
# ---------------------------------------------------------------------------

def test_missing_description_flagged():
    result = lint_file(FAIL_DIR / "missing_fields.md")
    rule_ids = [f.rule_id for f in result.findings]
    assert "QL-011" in rule_ids, "Expected QL-011 for missing description"
    assert "QL-012" in rule_ids, "Expected QL-012 for missing name"


# ---------------------------------------------------------------------------
# QL-009 — Description too short
# ---------------------------------------------------------------------------

def test_short_description_flagged():
    result = lint_file(FAIL_DIR / "short_description.md")
    rule_ids = [f.rule_id for f in result.findings]
    assert "QL-009" in rule_ids, f"Expected QL-009, got: {rule_ids}"
    error = next(f for f in result.findings if f.rule_id == "QL-009")
    assert error.severity == Severity.ERROR


# ---------------------------------------------------------------------------
# QL-004 / QL-006 / QL-015 — Weasel words and TODOs
# ---------------------------------------------------------------------------

def test_weasel_words_flagged():
    result = lint_file(FAIL_DIR / "weasel_skill.md")
    rule_ids = [f.rule_id for f in result.findings]
    # Should flag weasel intensifiers (basically, very, essentially)
    assert "QL-004" in rule_ids, f"Expected QL-004 (weasel intensifier), got: {rule_ids}"


def test_todo_flagged():
    result = lint_file(FAIL_DIR / "weasel_skill.md")
    rule_ids = [f.rule_id for f in result.findings]
    assert "QL-015" in rule_ids, f"Expected QL-015 (TODO marker), got: {rule_ids}"


def test_vague_verb_flagged():
    result = lint_file(FAIL_DIR / "weasel_skill.md")
    rule_ids = [f.rule_id for f in result.findings]
    assert "QL-008" in rule_ids, f"Expected QL-008 (vague verb), got: {rule_ids}"


# ---------------------------------------------------------------------------
# QL-015 — TODO inline
# ---------------------------------------------------------------------------

def test_todo_inline(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: todo_skill\nversion: '1.0.0'\n"
        "description: Fetches data from the remote API and returns structured JSON.\n---\n"
        "## Steps\n\nTODO: implement this\n"
    )
    result = lint_file(p)
    assert any(f.rule_id == "QL-015" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-013 — Name casing
# ---------------------------------------------------------------------------

def test_bad_name_casing(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: MyBadSkillName\nversion: '1.0.0'\n"
        "description: Fetches data from the remote API and returns structured JSON response.\n---\n"
    )
    result = lint_file(p)
    assert any(f.rule_id == "QL-013" for f in result.findings)


def test_good_snake_case_name(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: my_good_skill\nversion: '1.0.0'\n"
        "description: Fetches data from the remote API and returns structured JSON response.\n---\n"
    )
    result = lint_file(p)
    assert not any(f.rule_id == "QL-013" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-014 — Missing version
# ---------------------------------------------------------------------------

def test_missing_version_flagged(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: my_skill\n"
        "description: Fetches data from the remote API and returns structured JSON response.\n---\n"
    )
    result = lint_file(p)
    assert any(f.rule_id == "QL-014" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-010 — Description too long
# ---------------------------------------------------------------------------

def test_description_too_long(tmp_path):
    long_desc = " ".join(["word"] * 160)
    p = tmp_path / "SKILL.md"
    p.write_text(f"---\nname: my_skill\nversion: '1.0.0'\ndescription: {long_desc}\n---\n")
    result = lint_file(p)
    assert any(f.rule_id == "QL-010" for f in result.findings)


# ---------------------------------------------------------------------------
# Graph tests
# ---------------------------------------------------------------------------

def test_graph_cycle_detected(tmp_path):
    skill_a = tmp_path / "skill_a.md"
    skill_b = tmp_path / "skill_b.md"
    skill_a.write_text(
        "---\nname: skill_a\nversion: '1.0.0'\n"
        "description: Skill A fetches data from the API and returns JSON.\n"
        "invoke: skill_b\n---\n"
    )
    skill_b.write_text(
        "---\nname: skill_b\nversion: '1.0.0'\n"
        "description: Skill B processes data from the API and returns JSON.\n"
        "invoke: skill_a\n---\n"
    )
    from skillscan_lint.linter import lint_directory
    summary = lint_directory(tmp_path, recursive=False, include_graph=True)
    all_ids = [f.rule_id for r in summary.results for f in r.findings]
    assert "GR-001" in all_ids, f"Expected GR-001 (cycle), got: {all_ids}"


def test_graph_dangling_reference(tmp_path):
    skill_a = tmp_path / "skill_a.md"
    skill_a.write_text(
        "---\nname: skill_a\nversion: '1.0.0'\n"
        "description: Skill A fetches data from the API and returns JSON.\n"
        "invoke: nonexistent_skill\n---\n"
    )
    from skillscan_lint.linter import lint_directory
    summary = lint_directory(tmp_path, recursive=False, include_graph=True)
    all_ids = [f.rule_id for r in summary.results for f in r.findings]
    assert "GR-002" in all_ids, f"Expected GR-002 (dangling ref), got: {all_ids}"
