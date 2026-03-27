"""skill_schema.py — Shared skill schema loader for skillscan-lint.

Loads the canonical ``skill-schema.yaml`` using the following priority:

1. **From ``skillscan-security``** (preferred) — when ``skillscan-security`` is
   installed alongside ``skillscan-lint`` (e.g. via ``pip install
   skillscan-security[lint]``), the schema is read from the security package's
   bundled copy.  This guarantees both packages always share the same schema
   version without any manual sync step.

2. **From this package's own bundled copy** (fallback) — when ``skillscan-lint``
   is installed standalone (without ``skillscan-security``), the bundled copy
   at ``data/skill-schema.yaml`` is used instead.

The bundled copy in ``skillscan-lint`` is a snapshot that is kept in sync via
a CI job in ``skillscan-security`` that opens a PR here whenever the schema
changes.  In practice, users who install ``skillscan-security[lint]`` will
always get the live schema from the security package.

Usage::

    from skillscan_lint.skill_schema import (
        STANDARD_FM_KEYS,
        HIGH_RISK_UNKNOWN_KEYS,
        GRAPH_EDGE_KEYS,
        TOOL_RISK,
        HIGH_RISK_TOOLS,
    )
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Schema loader — tries skillscan-security first, falls back to own bundle
# ---------------------------------------------------------------------------

def _load_schema() -> dict[str, Any]:
    """Load skill-schema.yaml, preferring the skillscan-security copy."""
    # Strategy 1: use skillscan-security's skill_schema module directly
    try:
        from skillscan.skill_schema import _load_schema as _sec_load  # type: ignore[import]
        return _sec_load()
    except ImportError:
        pass

    # Strategy 2: use importlib.resources to read skillscan-security's data file
    try:
        from importlib.resources import files as _files
        schema_bytes = _files("skillscan.data").joinpath("skill-schema.yaml").read_bytes()
        return yaml.safe_load(schema_bytes)
    except (ImportError, FileNotFoundError, ModuleNotFoundError):
        pass

    # Strategy 3: fall back to this package's own bundled copy
    try:
        from importlib.resources import files as _files
        schema_bytes = _files("skillscan_lint.data").joinpath("skill-schema.yaml").read_bytes()
        return yaml.safe_load(schema_bytes)
    except (ImportError, FileNotFoundError):
        pass

    # Last resort: look for the file relative to this module
    _here = Path(__file__).parent
    for candidate in [
        _here / "data" / "skill-schema.yaml",
        _here.parent / "data" / "skill-schema.yaml",
    ]:
        if candidate.exists():
            return yaml.safe_load(candidate.read_bytes())

    raise FileNotFoundError(
        "skill-schema.yaml not found. Install skillscan-security or reinstall skillscan-lint."
    )


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    return _load_schema()


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_standard_fm_keys() -> frozenset[str]:
    return frozenset(_schema().get("standard_frontmatter_keys", []))


@lru_cache(maxsize=1)
def get_high_risk_unknown_keys() -> frozenset[str]:
    return frozenset(_schema().get("high_risk_unknown_keys", []))


@lru_cache(maxsize=1)
def get_graph_edge_keys() -> tuple[str, ...]:
    return tuple(_schema().get("graph_edge_keys", []))


@lru_cache(maxsize=1)
def get_tool_risk() -> dict[str, int]:
    tiers: dict[str, Any] = _schema().get("tool_risk_tiers", {})
    result: dict[str, int] = {}
    tier_map = {"high": 3, "medium": 2, "low": 1}
    for tier_name, tools in tiers.items():
        tier_value = tier_map.get(tier_name, 1)
        for tool in (tools or []):
            result[tool.lower()] = tier_value
    return result


# Module-level aliases
STANDARD_FM_KEYS: frozenset[str] = get_standard_fm_keys()
HIGH_RISK_UNKNOWN_KEYS: frozenset[str] = get_high_risk_unknown_keys()
GRAPH_EDGE_KEYS: tuple[str, ...] = get_graph_edge_keys()
TOOL_RISK: dict[str, int] = get_tool_risk()

HIGH_RISK_TOOLS: frozenset[str] = frozenset(t for t, v in TOOL_RISK.items() if v >= 3)
MEDIUM_RISK_TOOLS: frozenset[str] = frozenset(t for t, v in TOOL_RISK.items() if v == 2)
