"""Skill invocation graph analyzer for skillscan-lint.

Builds a directed graph of skill-to-skill invocations and detects:
- GR-001  Cycles (recursive invocation chains)
- GR-002  Dangling references (skill invokes a skill that doesn't exist)
- GR-003  Orphaned entry-point skills (invokes others but is never invoked)
- GR-004  Hub skills (unusually high in-degree — single point of failure)
- GR-005  Undocumented dependency (referenced skill has no Usage/Overview section)
- GR-006  Broken intra-skill file reference (Markdown link points to a .md file that doesn't exist)

Edge resolution — in order of reliability:
1. Front-matter keys (invoke/calls/depends_on/uses/requires):
   - If the value looks like a file path (contains "/" or ends in ".md"),
     resolve it relative to the skill file's directory and look up the
     target by resolved path.
   - Otherwise treat it as a skill name and look up by name or stem.
2. Markdown link hrefs in the body that point to .md files:
   [label](./path/to/SKILL.md)  ->  resolved as a file path.
3. Prose pattern matching is intentionally NOT used — it generates too
   many false positives.  Only explicit declarations and file links count.
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

# ---------------------------------------------------------------------------
# Markdown link extraction — only href values ending in .md
# ---------------------------------------------------------------------------
_MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")

_FRONTMATTER_INVOKE_KEYS = ("invoke", "calls", "depends_on", "uses", "requires")

# Heading patterns that count as documentation
_DOC_HEADING_RE = re.compile(
    r"^#{1,3}\s*(usage|overview|description|purpose|when to use|getting started)",
    re.IGNORECASE | re.MULTILINE,
)


def _skill_name(path: Path, parsed: dict[str, Any]) -> str:
    """Derive the canonical skill name from parsed front-matter or filename."""
    return str(parsed.get("name", path.stem))


def _resolve_ref(
    raw: str,
    source_path: Path,
    name_index: dict[str, str],
    path_index: dict[str, str],
) -> str | None:
    """Resolve a raw reference string to a canonical skill name.

    Returns the canonical name if found, or the raw string as a sentinel
    for unresolvable references (which will generate a GR-002 finding).
    Returns None only if the raw value is empty/invalid.
    """
    raw = raw.strip().strip("'\"")
    if not raw:
        return None

    is_path_like = "/" in raw or raw.endswith(".md")

    if is_path_like:
        try:
            resolved = (source_path.parent / raw).resolve()
            key = str(resolved)
            if key in path_index:
                return path_index[key]
        except (OSError, ValueError):
            pass
        # Path-like but not found — return raw so caller records a dangling edge
        return raw

    # Exact name lookup
    if raw in name_index:
        return name_index[raw]

    # Case-insensitive stem lookup
    for name, canonical in name_index.items():
        if name.lower() == raw.lower():
            return canonical

    # Not found — return raw so caller records a dangling edge
    return raw


def _extract_refs_from_frontmatter(
    parsed: dict[str, Any],
    source_path: Path,
    name_index: dict[str, str],
    path_index: dict[str, str],
) -> list[str]:
    """Extract invocation targets from YAML front-matter keys."""
    targets: list[str] = []
    for key in _FRONTMATTER_INVOKE_KEYS:
        val = parsed.get(key)
        if val is None:
            continue
        if isinstance(val, str):
            items = [v.strip() for v in re.split(r"[,\s]+", val) if v.strip()]
        elif isinstance(val, list):
            items = [str(v).strip() for v in val if v]
        else:
            continue
        for item in items:
            resolved = _resolve_ref(item, source_path, name_index, path_index)
            if resolved and resolved not in targets:
                targets.append(resolved)
    return targets


def _extract_refs_from_body(
    body: str,
    source_path: Path,
    name_index: dict[str, str],
    path_index: dict[str, str],
) -> list[str]:
    """Extract cross-skill invocation targets from Markdown link hrefs in the body.

    Only links that resolve to another SKILL.md (or YAML skill) entry point
    are treated as cross-skill invocations.  Links to reference docs, README
    files, and other supporting .md files within a skill package are intra-skill
    content and are NOT included here (they are checked by GR-006 instead).
    """
    targets: list[str] = []
    for m in _MD_LINK_RE.finditer(body):
        href = m.group(1).strip()
        if href.startswith("#") or href.startswith("http"):
            continue
        if not (href.endswith(".md") or "/" in href):
            continue
        # Only follow links that point to a skill entry point (SKILL.md / YAML)
        try:
            resolved_path = (source_path.parent / href).resolve()
        except (OSError, ValueError):
            continue
        if not _is_skill_entry(resolved_path):
            continue
        resolved = _resolve_ref(href, source_path, name_index, path_index)
        if resolved and resolved not in targets:
            targets.append(resolved)
    return targets


def _has_docs(parsed: dict[str, Any]) -> bool:
    """Return True if the skill has at least one documentation heading."""
    body = parsed.get("_body", "")
    return bool(_DOC_HEADING_RE.search(body))


def _is_skill_entry(path: Path) -> bool:
    """Return True if this file is a skill entry point (SKILL.md or *.yaml/yml).

    Reference docs, README files, and other .md files within a skill package
    are supporting material — they are NOT graph nodes.  Only files named
    exactly 'SKILL.md' (case-insensitive) or YAML skill definitions are
    treated as skill nodes in the invocation graph.
    """
    name = path.name.lower()
    return name == "skill.md" or path.suffix.lower() in (".yaml", ".yml")


def build_skill_graph(
    skill_files: list[tuple[Path, str, dict[str, Any]]],
) -> tuple["nx.DiGraph", dict[str, Path]]:
    """Build a directed graph from a list of (path, content, parsed) tuples.

    Only SKILL.md / YAML skill files are graph nodes.  Other .md files
    (reference docs, READMEs, etc.) are supporting material and are excluded
    from the graph — they are checked separately by GR-006.

    Returns (graph, name_to_path).
    """
    if not HAS_NX:
        raise ImportError(
            "networkx is required for graph analysis. "
            "Install with: pip install networkx"
        )

    g: nx.DiGraph = nx.DiGraph()
    name_to_path: dict[str, Path] = {}
    name_index: dict[str, str] = {}
    path_index: dict[str, str] = {}

    # Only SKILL.md / YAML files are graph nodes
    entry_files = [(p, c, d) for p, c, d in skill_files if _is_skill_entry(p)]

    for path, _content, parsed in entry_files:
        name = _skill_name(path, parsed)
        g.add_node(name, path=path, has_docs=_has_docs(parsed))
        name_to_path[name] = path
        name_index[name] = name
        path_index[str(path.resolve())] = name

    for path, _content, parsed in entry_files:
        src = _skill_name(path, parsed)
        body = parsed.get("_body", "")

        fm_targets = _extract_refs_from_frontmatter(parsed, path, name_index, path_index)
        body_targets = _extract_refs_from_body(body, path, name_index, path_index)

        for target in fm_targets + body_targets:
            if target != src:
                g.add_edge(src, target)

    return g, name_to_path


# Backward-compatible alias
build_graph = build_skill_graph


def analyze_graph(
    skill_files: list[tuple[Path, str, dict[str, Any]]],
) -> list[LintFinding]:
    """Run all graph-level checks and return findings."""
    if not HAS_NX:
        return []
    if not skill_files:
        return []

    g, name_to_path = build_skill_graph(skill_files)

    # Rebuild path_index for GR-006 (maps resolved path str -> canonical skill name)
    path_index: dict[str, str] = {
        str(path.resolve()): _skill_name(path, parsed)
        for path, _content, parsed in skill_files
    }

    parsed_by_name: dict[str, dict[str, Any]] = {
        _skill_name(p, parsed): parsed
        for p, _content, parsed in skill_files
    }

    findings: list[LintFinding] = []

    # --- GR-001: Cycle detection ---
    try:
        cycles = list(nx.simple_cycles(g))
    except Exception:  # noqa: BLE001
        cycles = []
    for cycle in cycles:
        cycle_str = " -> ".join(cycle + [cycle[0]])
        path = name_to_path.get(cycle[0], Path(cycle[0]))
        findings.append(LintFinding(
            rule_id="GR-001",
            severity=Severity.ERROR,
            category=Category.GRAPH,
            message=f"Recursive invocation cycle detected: {cycle_str}",
            path=path,
            suggestion="Break the cycle by introducing a conditional or removing the back-edge.",
        ))

    # --- GR-002: Dangling reference detection ---
    known_skills = set(name_to_path.keys())
    for src, dst in g.edges():
        if dst not in known_skills:
            path = name_to_path.get(src, Path(src))
            findings.append(LintFinding(
                rule_id="GR-002",
                severity=Severity.ERROR,
                category=Category.GRAPH,
                message=f'Skill "{src}" references "{dst}" which does not exist in the scanned set.',
                path=path,
                suggestion=f'Create a skill named "{dst}" or correct the reference.',
            ))

    # --- GR-003: Orphan detection ---
    all_targets = {dst for _, dst in g.edges()}
    for name, path in name_to_path.items():
        if name not in all_targets:
            skill_data = parsed_by_name.get(name, {})
            is_entry = skill_data.get("entry_point", False) or skill_data.get("entrypoint", False)
            if not is_entry and g.out_degree(name) > 0:
                findings.append(LintFinding(
                    rule_id="GR-003",
                    severity=Severity.INFO,
                    category=Category.GRAPH,
                    message=(
                        f'Skill "{name}" references other skills but is never '
                        "referenced itself. Consider marking it as "
                        "'entry_point: true' if intentional."
                    ),
                    path=path,
                    suggestion="Add 'entry_point: true' to the front-matter if this is a top-level skill.",
                ))

    # --- GR-004: Hub detection ---
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
                    f'Skill "{name}" is referenced by {in_deg} other skills — '
                    "high coupling creates a single point of failure."
                ),
                path=path,
                suggestion="Consider splitting this skill or introducing an abstraction layer.",
            ))

    # --- GR-005: Undocumented dependency ---
    for name in g.nodes():
        if g.in_degree(name) > 0:
            parsed = parsed_by_name.get(name, {})
            if not _has_docs(parsed):
                path = name_to_path.get(name, Path(name))
                findings.append(LintFinding(
                    rule_id="GR-005",
                    severity=Severity.WARNING,
                    category=Category.GRAPH,
                    message=(
                        f'Skill "{name}" is referenced by other skills but has '
                        "no Usage, Overview, or Description section."
                    ),
                    path=path,
                    suggestion=(
                        "Add a ## Usage or ## Overview section so callers "
                        "understand how to invoke this skill."
                    ),
                ))

    # --- GR-006: Broken intra-skill file references ---
    # These are Markdown links within a single skill's files that point to
    # sibling .md files (e.g. references/troubleshooting.md) that don't exist.
    # This is distinct from cross-skill dangling refs (GR-002): GR-002 is about
    # skills referencing other skills; GR-006 is about a skill's own internal docs.
    for path, _content, parsed in skill_files:
        body = parsed.get("_body", "")
        for m in _MD_LINK_RE.finditer(body):
            href = m.group(1).strip()
            if href.startswith("#") or href.startswith("http"):
                continue
            if not href.endswith(".md"):
                continue
            # Resolve relative to the skill file's directory
            try:
                target = (path.parent / href).resolve()
            except (OSError, ValueError):
                continue
            # Only flag if the href doesn't resolve to a known skill node
            # (those are handled by GR-002) and the file doesn't exist on disk
            target_name = path_index.get(str(target))
            if target_name is not None:
                continue  # cross-skill ref — GR-002 handles it
            if not target.exists():
                findings.append(LintFinding(
                    rule_id="GR-006",
                    severity=Severity.WARNING,
                    category=Category.GRAPH,
                    message=(
                        f'Broken file reference in "{_skill_name(path, parsed)}": '
                        f'"{href}" does not exist.'
                    ),
                    path=path,
                    suggestion=(
                        f'Create the file at "{href}" relative to this skill, '
                        "or remove the link."
                    ),
                ))

    return findings
