"""Skill invocation graph analyzer for skillscan-lint.

Builds a directed graph of skill-to-skill invocations and detects:
- Cycles (recursive invocation chains)
- Dangling references (skill invokes a skill that doesn't exist in the scanned set)
- Orphaned skills (skills that are never invoked and have no entry point marker)
- Hub skills (skills with unusually high in-degree — potential single points of failure)

Invocation detection: scans for patterns like:
  invoke: other_skill
  calls: [skill_a, skill_b]
  depends_on: skill_c
  uses: skill_d
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

from skillscan_lint.models import Category, LintFinding, Severity

# Patterns that indicate one skill invoking another
_INVOKE_YAML_KEYS = re.compile(
    r"^\s*(?:invoke|calls?|depends_on|uses?|requires?)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

_INVOKE_INLINE = re.compile(
    r"(?:invoke|call|use|run)\s+[`'\"]?([a-z][a-z0-9_\-]+)[`'\"]?",
    re.IGNORECASE,
)


def _extract_invocations(content: str, parsed: dict[str, Any] | None = None) -> list[str]:
    """Return skill names that this skill invokes."""
    targets: list[str] = []

    # Check parsed front-matter keys directly (handles YAML-parsed invoke/calls/depends_on)
    if parsed:
        for key in ("invoke", "calls", "depends_on", "uses", "requires"):
            val = parsed.get(key)
            if val is None:
                continue
            if isinstance(val, str):
                items = [v.strip() for v in re.split(r"[,\s]+", val) if v.strip()]
            elif isinstance(val, list):
                items = [str(v).strip() for v in val if v]
            else:
                items = []
            for item in items:
                item = item.strip("'\"")
                if item and re.match(r"^[a-z][a-z0-9_\-]*$", item) and item not in targets:
                    targets.append(item)

    # Also scan raw content for inline invocation patterns
    for m in _INVOKE_YAML_KEYS.finditer(content):
        raw = m.group(1).strip()
        raw = raw.strip("[]")
        for item in re.split(r"[,\s]+", raw):
            item = item.strip().strip("'\"").strip("-").strip()
            if item and re.match(r"^[a-z][a-z0-9_\-]*$", item) and item not in targets:
                targets.append(item)

    for m in _INVOKE_INLINE.finditer(content):
        name = m.group(1)
        if name not in targets:
            targets.append(name)

    return targets


def _skill_name(path: Path, parsed: dict[str, Any]) -> str:
    """Derive the canonical skill name from parsed front-matter or filename."""
    return str(parsed.get("name", path.stem))


def build_graph(
    skill_files: list[tuple[Path, str, dict[str, Any]]],
) -> nx.DiGraph:
    """Build a directed graph from a list of (path, content, parsed) tuples."""
    if not HAS_NX:
        raise ImportError("networkx is required for graph analysis. Install with: pip install networkx")

    g: nx.DiGraph = nx.DiGraph()

    # First pass: register all known skills as nodes
    name_to_path: dict[str, Path] = {}
    for path, content, parsed in skill_files:
        name = _skill_name(path, parsed)
        g.add_node(name, path=path)
        name_to_path[name] = path

    # Second pass: add edges for invocations
    for path, content, parsed in skill_files:
        src = _skill_name(path, parsed)
        for target in _extract_invocations(content, parsed):
            g.add_edge(src, target)

    return g, name_to_path


def analyze_graph(
    skill_files: list[tuple[Path, str, dict[str, Any]]],
) -> list[LintFinding]:
    """Run all graph-level checks and return findings."""
    if not HAS_NX:
        return []

    if not skill_files:
        return []

    g, name_to_path = build_graph(skill_files)
    findings: list[LintFinding] = []

    # --- Cycle detection ---
    try:
        cycles = list(nx.simple_cycles(g))
    except Exception:
        cycles = []

    for cycle in cycles:
        cycle_str = " → ".join(cycle + [cycle[0]])
        # Attribute the finding to the first skill in the cycle that we have a path for
        path = name_to_path.get(cycle[0], Path(cycle[0]))
        findings.append(LintFinding(
            rule_id="GR-001",
            severity=Severity.ERROR,
            category=Category.GRAPH,
            message=f"Recursive invocation cycle detected: {cycle_str}",
            path=path,
            suggestion="Break the cycle by introducing a conditional or removing the back-edge.",
        ))

    # --- Dangling reference detection ---
    known_skills = set(name_to_path.keys())
    for src, dst in g.edges():
        if dst not in known_skills:
            path = name_to_path.get(src, Path(src))
            findings.append(LintFinding(
                rule_id="GR-002",
                severity=Severity.ERROR,
                category=Category.GRAPH,
                message=f"Skill \"{src}\" invokes \"{dst}\" which does not exist in the scanned set.",
                path=path,
                suggestion=f"Create a skill named \"{dst}\" or correct the invocation target.",
            ))

    # --- Orphan detection (skills never invoked, no entry_point marker) ---
    all_targets = {dst for _, dst in g.edges()}
    for name, path in name_to_path.items():
        if name not in all_targets:
            # Check if the skill declares itself as an entry point
            skill_data = next(
                (parsed for p, _, parsed in skill_files if _skill_name(p, parsed) == name),
                {},
            )
            is_entry = skill_data.get("entry_point", False) or skill_data.get("entrypoint", False)
            if not is_entry and g.out_degree(name) > 0:
                # Only flag as orphan if it invokes others but is never invoked itself
                # (pure leaf skills that are never invoked are fine)
                findings.append(LintFinding(
                    rule_id="GR-003",
                    severity=Severity.INFO,
                    category=Category.GRAPH,
                    message=(
                        f"Skill \"{name}\" invokes other skills but is never invoked itself. "
                        "Consider marking it as 'entry_point: true' if intentional."
                    ),
                    path=path,
                    suggestion="Add 'entry_point: true' to the front-matter if this is a top-level skill.",
                ))

    # --- Hub detection (high in-degree) ---
    HUB_THRESHOLD = 5
    for name in g.nodes():
        in_deg = g.in_degree(name)
        if in_deg >= HUB_THRESHOLD:
            path = name_to_path.get(name, Path(name))
            findings.append(LintFinding(
                rule_id="GR-004",
                severity=Severity.WARNING,
                category=Category.GRAPH,
                message=(
                    f"Skill \"{name}\" is invoked by {in_deg} other skills — "
                    "high coupling creates a single point of failure."
                ),
                path=path,
                suggestion="Consider splitting this skill or introducing an abstraction layer.",
            ))

    return findings
