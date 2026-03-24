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
    # Skills must be SKILL.md files (in subdirs) to be treated as graph nodes
    dir_a = tmp_path / "skill-a"
    dir_b = tmp_path / "skill-b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "SKILL.md").write_text(
        "---\nname: skill_a\nversion: '1.0.0'\n"
        "description: Skill A fetches data from the API and returns JSON.\n"
        "invoke: skill_b\n---\n"
    )
    (dir_b / "SKILL.md").write_text(
        "---\nname: skill_b\nversion: '1.0.0'\n"
        "description: Skill B processes data from the API and returns JSON.\n"
        "invoke: skill_a\n---\n"
    )
    from skillscan_lint.linter import lint_directory
    summary = lint_directory(tmp_path, recursive=True, include_graph=True)
    all_ids = [f.rule_id for r in summary.results for f in r.findings]
    assert "GR-001" in all_ids, f"Expected GR-001 (cycle), got: {all_ids}"


def test_graph_dangling_reference(tmp_path):
    dir_a = tmp_path / "skill-a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text(
        "---\nname: skill_a\nversion: '1.0.0'\n"
        "description: Skill A fetches data from the API and returns JSON.\n"
        "invoke: nonexistent_skill\n---\n"
    )
    from skillscan_lint.linter import lint_directory
    summary = lint_directory(tmp_path, recursive=True, include_graph=True)
    all_ids = [f.rule_id for r in summary.results for f in r.findings]
    assert "GR-002" in all_ids, f"Expected GR-002 (dangling ref), got: {all_ids}"


# ---------------------------------------------------------------------------
# QL-016 — Weasel superlatives
# ---------------------------------------------------------------------------

def test_superlative_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\ndescription: "
        "The best and most advanced tool for searching the web.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-016" in rule_ids, f"Expected QL-016 (superlative), got: {rule_ids}"


def test_no_superlative_clean(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Searches the web and returns the top 5 results.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-016" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-017 — Nominalisations
# ---------------------------------------------------------------------------

def test_nominalisation_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Handles the optimization of search queries for better results.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-017" in rule_ids, f"Expected QL-017 (nominalisation), got: {rule_ids}"


# ---------------------------------------------------------------------------
# QL-018 — Redundant phrases
# ---------------------------------------------------------------------------

def test_redundant_phrase_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Returns the end result of the search operation.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-018" in rule_ids, f"Expected QL-018 (redundant phrase), got: {rule_ids}"


# ---------------------------------------------------------------------------
# QL-019 — Buzzwords
# ---------------------------------------------------------------------------

def test_buzzword_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: A game-changer that leverages synergy to improve outcomes.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-019" in rule_ids, f"Expected QL-019 (buzzword), got: {rule_ids}"


# ---------------------------------------------------------------------------
# QL-020 — Vague quantifiers
# ---------------------------------------------------------------------------

def test_vague_quantifier_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches several results from various sources.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-020" in rule_ids, f"Expected QL-020 (vague quantifier), got: {rule_ids}"


def test_specific_quantifier_clean(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches up to 10 results from the configured search engine.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-020" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-021 — Undefined acronyms
# ---------------------------------------------------------------------------

def test_undefined_acronym_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Uses the SERP to retrieve organic search results.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-021" in rule_ids, f"Expected QL-021 (undefined acronym), got: {rule_ids}"


def test_known_acronym_not_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Calls an API endpoint and returns JSON results.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-021" for f in result.findings)


def test_expanded_acronym_not_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Uses the Search Engine Results Page (SERP) to find results.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-021" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-022 — Double negatives
# ---------------------------------------------------------------------------

def test_double_negative_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: It is not uncommon for this skill to return empty results.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-022" in rule_ids, f"Expected QL-022 (double negative), got: {rule_ids}"


# ---------------------------------------------------------------------------
# QL-023 — Missing examples
# ---------------------------------------------------------------------------

def test_missing_examples_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches weather data for a given city.\n---\n"
        "\n## Usage\n\nCall this skill with a city name.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-023" in rule_ids, f"Expected QL-023 (missing examples), got: {rule_ids}"


def test_yaml_examples_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches weather data for a given city.\n"
        "examples:\n  - input: London\n    output: 15C, cloudy\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-023" for f in result.findings)


def test_markdown_examples_heading_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches weather data for a given city.\n---\n"
        "\n## Examples\n\nCall with `get_weather(city='London')`.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-023" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-024 — Missing tags
# ---------------------------------------------------------------------------

def test_missing_tags_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches weather data for a given city.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-024" in rule_ids, f"Expected QL-024 (missing tags), got: {rule_ids}"


def test_tags_present_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\ntags: [weather, search]\n"
        "description: Fetches weather data for a given city.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-024" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-025 — Imperative mood
# ---------------------------------------------------------------------------

def test_weak_opener_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: This skill fetches weather data for a given city.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-025" in rule_ids, f"Expected QL-025 (imperative mood), got: {rule_ids}"


def test_imperative_opener_clean(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0'\n"
        "description: Fetches weather data for a given city and returns temperature.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-025" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-026 — Unknown frontmatter keys
# ---------------------------------------------------------------------------

def test_unknown_frontmatter_key_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n"
        "custom_field: some_value\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-026" in rule_ids, f"Expected QL-026 (unknown frontmatter key), got: {rule_ids}"


def test_standard_frontmatter_keys_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\ntags: [search]\n"
        "allowed-tools: [web_search]\nexamples:\n  - input: test\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-026" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-027 — Invalid version string
# ---------------------------------------------------------------------------

def test_invalid_version_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: 'v1.0'\n"
        "description: Fetches data.\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-027" in rule_ids, f"Expected QL-027 (invalid version), got: {rule_ids}"


def test_valid_semver_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.2.3'\n"
        "description: Fetches data.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-027" for f in result.findings)


def test_semver_with_prerelease_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '2.0.0-beta.1'\n"
        "description: Fetches data.\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-027" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-028 — Vague tool references
# ---------------------------------------------------------------------------

def test_vague_tool_reference_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Usage\n\nUse the tool to search for results.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-028" in rule_ids, f"Expected QL-028 (vague tool reference), got: {rule_ids}"


def test_specific_tool_name_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Usage\n\nCall search_web(query=...) to search for results.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-028" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-029 — Description capability mismatch
# ---------------------------------------------------------------------------

def test_capability_mismatch_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Executes shell commands to deploy the service.\n"
        "allowed-tools: [web_search]\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-029" in rule_ids, f"Expected QL-029 (capability mismatch), got: {rule_ids}"


def test_capability_declared_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Executes shell commands to deploy the service.\n"
        "allowed-tools: [Bash, web_search]\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-029" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-030 — Unjustified high-risk tool
# ---------------------------------------------------------------------------

def test_unjustified_bash_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Searches the web for information.\n"
        "allowed-tools: [Bash]\n---\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-030" in rule_ids, f"Expected QL-030 (unjustified Bash), got: {rule_ids}"


def test_justified_bash_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Automates CI/CD pipeline by running build scripts.\n"
        "allowed-tools: [Bash]\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-030" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-031 — Missing changelog
# ---------------------------------------------------------------------------

def test_missing_changelog_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Usage\n\nCall this skill.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-031" in rule_ids, f"Expected QL-031 (missing changelog), got: {rule_ids}"


def test_yaml_changelog_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n"
        "changelog:\n  - version: '1.0.0'\n    note: Initial release\n---\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-031" for f in result.findings)


def test_markdown_changelog_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Changelog\n\n- 1.0.0: Initial release\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-031" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-032 — Missing Inputs/Outputs sections
# ---------------------------------------------------------------------------

def test_missing_inputs_outputs_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Usage\n\nCall this skill.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-032" in rule_ids, f"Expected QL-032 (missing inputs/outputs), got: {rule_ids}"


def test_inputs_section_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Inputs\n\n- query: string\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-032" for f in result.findings)


def test_outputs_section_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Outputs\n\n- result: string\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-032" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-033 — Missing When to Use section
# ---------------------------------------------------------------------------

def test_missing_when_to_use_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## Usage\n\nCall this skill.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-033" in rule_ids, f"Expected QL-033 (missing when to use), got: {rule_ids}"


def test_when_to_use_section_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches data.\n---\n"
        "\n## When to Use\n\nUse this skill when you need to fetch data.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-033" for f in result.findings)


# ---------------------------------------------------------------------------
# QL-034 — Missing Prerequisites section for CLI tools
# ---------------------------------------------------------------------------

def test_cli_tool_without_prerequisites_flagged(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Deploys to Kubernetes.\n---\n"
        "\n## Usage\n\nRun kubectl apply -f deployment.yaml to deploy.\n"
    )
    result = lint_file(skill)
    rule_ids = {f.rule_id for f in result.findings}
    assert "QL-034" in rule_ids, f"Expected QL-034 (missing prerequisites), got: {rule_ids}"


def test_prerequisites_section_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Deploys to Kubernetes.\n---\n"
        "\n## Prerequisites\n\n- kubectl >= 1.28\n- kubeconfig configured\n"
        "\n## Usage\n\nRun kubectl apply -f deployment.yaml to deploy.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-034" for f in result.findings)


def test_compatibility_field_satisfies_rule(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Deploys to Kubernetes.\n"
        "compatibility:\n  kubectl: '>=1.28'\n---\n"
        "\n## Usage\n\nRun kubectl apply -f deployment.yaml to deploy.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-034" for f in result.findings)


def test_no_cli_tools_no_flag(tmp_path):
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\nname: my_skill\nversion: '1.0.0'\n"
        "description: Fetches weather data.\n---\n"
        "\n## Usage\n\nCall this skill with a city name.\n"
    )
    result = lint_file(skill)
    assert not any(f.rule_id == "QL-034" for f in result.findings)
