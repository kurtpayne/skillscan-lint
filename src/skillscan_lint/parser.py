"""Skill file parser for skillscan-lint.

Supports:
- SKILL.md files with YAML front-matter (--- delimited)
- Standalone .yaml / .yml skill definitions
- Plain .md files (parsed as body-only, no front-matter)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


class ParseError(Exception):
    pass


def parse_skill_file(path: Path) -> tuple[str, dict[str, Any]]:
    """Parse a skill file and return (raw_content, parsed_dict).

    The parsed dict always has a '_body' key containing the markdown body
    (everything after the front-matter), and '_path' with the file path.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ParseError(f"Skipping binary/non-UTF-8 file: {path}")
    except OSError as e:
        raise ParseError(f"Cannot read {path}: {e}") from e

    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return _parse_yaml(path, content)
    else:
        # .md or SKILL.md — try front-matter first
        return _parse_markdown(path, content)


def _parse_yaml(path: Path, content: str) -> tuple[str, dict[str, Any]]:
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        raise ParseError(f"YAML parse error in {path}: {e}") from e
    if not isinstance(data, dict):
        data = {}
    data["_body"] = ""
    data["_path"] = str(path)
    return content, data


def _parse_markdown(path: Path, content: str) -> tuple[str, dict[str, Any]]:
    m = FRONTMATTER_RE.match(content)
    if m:
        yaml_block, body = m.group(1), m.group(2)
        try:
            data = yaml.safe_load(yaml_block) or {}
        except yaml.YAMLError as e:
            raise ParseError(f"YAML front-matter parse error in {path}: {e}") from e
        if not isinstance(data, dict):
            data = {}
    else:
        # No front-matter — treat entire content as body
        data = {}
        body = content

    data["_body"] = body.strip()
    data["_path"] = str(path)
    return content, data


def is_skill_file(path: Path) -> bool:
    """Return True if the path looks like a skill file we should lint."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    return name == "skill.md" or suffix in (".yaml", ".yml", ".md")
