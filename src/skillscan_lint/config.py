"""config.py — .skillscan-lint.toml configuration loader.

Searches for a configuration file in the following order:
  1. Path passed explicitly via --config CLI flag
  2. .skillscan-lint.toml in the current working directory
  3. skillscan-lint.toml in the current working directory
  4. .skillscan-lint.toml in each parent directory up to the filesystem root

If no file is found, a default LintConfig is returned.

Example .skillscan-lint.toml
-----------------------------
[rules]
# Disable individual rules
disable = ["QL-003", "QL-005"]

# Override severity for a rule
[rules.overrides]
"QL-017" = "error"   # promote nominalisation to error
"QL-004" = "info"    # demote weasel intensifiers to info

[thresholds]
# Maximum word count for a description field (default: 80)
max_description_words = 100
# Minimum word count for a description field (default: 10)
min_description_words = 5
# Maximum sentence length in words (default: 30)
max_sentence_length = 35

[graph]
# Skip graph analysis entirely
skip_graph = false

[output]
# Default output format: rich | compact | json
format = "rich"
# Default fail-on level: error | warning | never
fail_on = "error"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RulesConfig:
    """Per-rule configuration."""

    disable: list[str] = field(default_factory=list)
    """Rule IDs to disable globally."""

    overrides: dict[str, str] = field(default_factory=dict)
    """Map of rule_id → severity override ('error' | 'warning' | 'info')."""


@dataclass
class ThresholdsConfig:
    """Numeric thresholds that rules use."""

    max_description_words: int = 80
    min_description_words: int = 10
    max_sentence_length: int = 30


@dataclass
class GraphConfig:
    """Graph analysis settings."""

    skip_graph: bool = False


@dataclass
class OutputConfig:
    """Default output settings."""

    format: str = "rich"
    fail_on: str = "error"


@dataclass
class LintConfig:
    """Top-level configuration object."""

    rules: RulesConfig = field(default_factory=RulesConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # Path of the config file that was loaded (None = defaults)
    source: Path | None = None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_CONFIG_FILENAMES = (".skillscan-lint.toml", "skillscan-lint.toml")


def _find_config_file(start: Path) -> Path | None:
    """Walk up from *start* looking for a config file."""
    candidate = start if start.is_dir() else start.parent
    while True:
        for name in _CONFIG_FILENAMES:
            p = candidate / name
            if p.is_file():
                return p
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def load_config(
    explicit_path: Path | None = None,
    search_from: Path | None = None,
) -> LintConfig:
    """Load and return a LintConfig.

    Parameters
    ----------
    explicit_path:
        If provided, load this file and raise FileNotFoundError if missing.
    search_from:
        Directory (or file) from which to start the upward search.
        Defaults to ``Path.cwd()``.
    """
    config_path: Path | None = None

    if explicit_path is not None:
        if not explicit_path.is_file():
            raise FileNotFoundError(f"Config file not found: {explicit_path}")
        config_path = explicit_path
    else:
        config_path = _find_config_file(search_from or Path.cwd())

    if config_path is None:
        return LintConfig()

    return _parse_toml(config_path)


def _parse_toml(path: Path) -> LintConfig:
    """Parse a TOML config file into a LintConfig."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            logger.warning(
                "Cannot load %s: neither tomllib (Python 3.11+) nor tomli is available. "
                "Install tomli: pip install tomli",
                path,
            )
            return LintConfig(source=path)

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse config file %s: %s", path, exc)
        return LintConfig(source=path)

    cfg = LintConfig(source=path)

    # [rules]
    rules_raw = raw.get("rules", {})
    if isinstance(rules_raw, dict):
        disable = rules_raw.get("disable", [])
        if isinstance(disable, list):
            cfg.rules.disable = [str(d) for d in disable]

        overrides_raw = rules_raw.get("overrides", {})
        if isinstance(overrides_raw, dict):
            valid_severities = {"error", "warning", "info"}
            cfg.rules.overrides = {
                str(k): str(v) for k, v in overrides_raw.items() if str(v) in valid_severities
            }

    # [thresholds]
    thresh_raw = raw.get("thresholds", {})
    if isinstance(thresh_raw, dict):
        if "max_description_words" in thresh_raw:
            cfg.thresholds.max_description_words = int(thresh_raw["max_description_words"])
        if "min_description_words" in thresh_raw:
            cfg.thresholds.min_description_words = int(thresh_raw["min_description_words"])
        if "max_sentence_length" in thresh_raw:
            cfg.thresholds.max_sentence_length = int(thresh_raw["max_sentence_length"])

    # [graph]
    graph_raw = raw.get("graph", {})
    if isinstance(graph_raw, dict):
        if "skip_graph" in graph_raw:
            cfg.graph.skip_graph = bool(graph_raw["skip_graph"])

    # [output]
    output_raw = raw.get("output", {})
    if isinstance(output_raw, dict):
        if "format" in output_raw and output_raw["format"] in {"rich", "compact", "json", "sarif"}:
            cfg.output.format = str(output_raw["format"])
        if "fail_on" in output_raw and output_raw["fail_on"] in {"error", "warning", "never"}:
            cfg.output.fail_on = str(output_raw["fail_on"])

    logger.debug("Loaded config from %s", path)
    return cfg
