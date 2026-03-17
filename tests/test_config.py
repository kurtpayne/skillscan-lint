"""Tests for .skillscan-lint.toml config loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from skillscan_lint.config import LintConfig, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".skillscan-lint.toml"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------


def test_default_config_when_no_file(tmp_path: Path) -> None:
    """load_config returns defaults when no config file exists."""
    cfg = load_config(search_from=tmp_path)
    assert isinstance(cfg, LintConfig)
    assert cfg.rules.disable == []
    assert cfg.rules.overrides == {}
    assert cfg.thresholds.max_description_words == 80
    assert cfg.thresholds.min_description_words == 10
    assert cfg.thresholds.max_sentence_length == 30
    assert cfg.graph.skip_graph is False
    assert cfg.output.format == "rich"
    assert cfg.output.fail_on == "error"
    assert cfg.source is None


# ---------------------------------------------------------------------------
# Explicit path
# ---------------------------------------------------------------------------


def test_explicit_path_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(explicit_path=tmp_path / "nonexistent.toml")


def test_explicit_path_loads_correctly(tmp_path: Path) -> None:
    write_toml(
        tmp_path,
        """
        [rules]
        disable = ["QL-003", "QL-005"]
        """,
    )
    cfg = load_config(explicit_path=tmp_path / ".skillscan-lint.toml")
    assert "QL-003" in cfg.rules.disable
    assert "QL-005" in cfg.rules.disable
    assert cfg.source == tmp_path / ".skillscan-lint.toml"


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------


def test_auto_discovery_finds_file_in_cwd(tmp_path: Path) -> None:
    write_toml(tmp_path, "[output]\nformat = 'compact'\n")
    cfg = load_config(search_from=tmp_path)
    assert cfg.output.format == "compact"


def test_auto_discovery_walks_up(tmp_path: Path) -> None:
    """Config in parent directory is found when searching from a child."""
    write_toml(tmp_path, "[output]\nfail_on = 'warning'\n")
    child = tmp_path / "subdir"
    child.mkdir()
    cfg = load_config(search_from=child)
    assert cfg.output.fail_on == "warning"


# ---------------------------------------------------------------------------
# [rules] section
# ---------------------------------------------------------------------------


def test_rules_disable(tmp_path: Path) -> None:
    write_toml(tmp_path, '[rules]\ndisable = ["QL-016", "QL-019"]\n')
    cfg = load_config(search_from=tmp_path)
    assert set(cfg.rules.disable) == {"QL-016", "QL-019"}


def test_rules_overrides_valid(tmp_path: Path) -> None:
    write_toml(
        tmp_path,
        """
        [rules.overrides]
        "QL-017" = "error"
        "QL-004" = "info"
        """,
    )
    cfg = load_config(search_from=tmp_path)
    assert cfg.rules.overrides["QL-017"] == "error"
    assert cfg.rules.overrides["QL-004"] == "info"


def test_rules_overrides_invalid_severity_ignored(tmp_path: Path) -> None:
    write_toml(
        tmp_path,
        """
        [rules.overrides]
        "QL-017" = "critical"
        """,
    )
    cfg = load_config(search_from=tmp_path)
    assert "QL-017" not in cfg.rules.overrides


# ---------------------------------------------------------------------------
# [thresholds] section
# ---------------------------------------------------------------------------


def test_thresholds_override(tmp_path: Path) -> None:
    write_toml(
        tmp_path,
        """
        [thresholds]
        max_description_words = 120
        min_description_words = 3
        max_sentence_length = 40
        """,
    )
    cfg = load_config(search_from=tmp_path)
    assert cfg.thresholds.max_description_words == 120
    assert cfg.thresholds.min_description_words == 3
    assert cfg.thresholds.max_sentence_length == 40


# ---------------------------------------------------------------------------
# [graph] section
# ---------------------------------------------------------------------------


def test_graph_skip(tmp_path: Path) -> None:
    write_toml(tmp_path, "[graph]\nskip_graph = true\n")
    cfg = load_config(search_from=tmp_path)
    assert cfg.graph.skip_graph is True


# ---------------------------------------------------------------------------
# [output] section
# ---------------------------------------------------------------------------


def test_output_format_and_fail_on(tmp_path: Path) -> None:
    write_toml(tmp_path, '[output]\nformat = "json"\nfail_on = "never"\n')
    cfg = load_config(search_from=tmp_path)
    assert cfg.output.format == "json"
    assert cfg.output.fail_on == "never"


def test_output_invalid_format_ignored(tmp_path: Path) -> None:
    write_toml(tmp_path, '[output]\nformat = "xml"\n')
    cfg = load_config(search_from=tmp_path)
    assert cfg.output.format == "rich"  # default preserved


# ---------------------------------------------------------------------------
# Severity override integration with linter
# ---------------------------------------------------------------------------


def test_severity_override_applied(tmp_path: Path) -> None:
    """A severity override in config changes the finding severity."""
    from skillscan_lint.linter import lint_file

    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: test\nversion: 1.0\ndescription: This skill handles things very well.\n---\n"
    )
    # QL-004 (weasel intensifier "very") is INFO by default; override to error
    result = lint_file(skill, severity_overrides={"QL-004": "error"})
    ql004_findings = [f for f in result.findings if f.rule_id == "QL-004"]
    assert all(f.severity.value == "error" for f in ql004_findings), (
        "Expected QL-004 findings to be promoted to error"
    )


def test_severity_override_not_applied_when_empty(tmp_path: Path) -> None:
    """Without overrides, QL-004 stays at its default severity (warning)."""
    from skillscan_lint.linter import lint_file

    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: test\nversion: 1.0\ndescription: This skill handles things very well.\n---\n"
    )
    result = lint_file(skill)
    ql004_findings = [f for f in result.findings if f.rule_id == "QL-004"]
    assert all(f.severity.value == "warning" for f in ql004_findings), (
        "Expected QL-004 findings to remain at warning severity"
    )
