# skillscan-lint

[![CI](https://github.com/kurtpayne/skillscan-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/kurtpayne/skillscan-lint/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/skillscan-lint.svg)](https://pypi.org/project/skillscan-lint/)
[![Docker Hub](https://img.shields.io/docker/v/kurtpayne/skillscan-lint?label=docker)](https://hub.docker.com/r/kurtpayne/skillscan-lint)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

**Quality linter for AI agent skill files.** Catches weasel words, ambiguous instructions, missing metadata, and skill graph problems (cycles, dangling references, broken file links) before they reach production.

Works with skills from [skills.sh](https://skills.sh), [ClawHub](https://clawhub.ai), and any `SKILL.md`-based skill package.

---

## Install

```bash
pip install skillscan-lint
```

Or run without installing:

```bash
docker run --rm -v "$PWD:/work" kurtpayne/skillscan-lint scan /work/skills/
```

---

## Quick Start

```bash
# Lint a single skill file
skillscan-lint scan SKILL.md

# Lint an entire skills directory (including graph checks)
skillscan-lint scan ./skills/ --graph

# Output as JSON for CI integration
skillscan-lint scan ./skills/ --format json

# List all rules
skillscan-lint rules
```

### Example output

```
SKILL.md
  QL-004  WARNING  Weasel intensifier "basically" weakens the instruction.
  QL-009  ERROR    Description too short (8 words). Minimum is 10.
  QL-015  WARNING  TODO marker found — remove before publishing.
  GR-002  ERROR    Skill "data-fetcher" references "parser" which does not exist.
  GR-006  WARNING  Broken file reference: "references/auth.md" does not exist.

2 errors, 3 warnings
```

---

## Rules

skillscan-lint ships with two rule families:

### Quality rules (`QL-*`)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| QL-001 | WARNING | Passive voice in instructions |
| QL-004 | WARNING | Weasel intensifiers (`basically`, `very`, `essentially`) |
| QL-008 | WARNING | Vague verbs (`handle`, `manage`, `deal with`) |
| QL-009 | ERROR | Description too short (< 10 words) |
| QL-010 | WARNING | Description too long (> 150 words) |
| QL-011 | ERROR | Missing `description` field |
| QL-012 | ERROR | Missing `name` field |
| QL-013 | WARNING | Name not in `snake_case` |
| QL-014 | WARNING | Missing `version` field |
| QL-015 | WARNING | TODO/FIXME marker in body |
| QL-016 | WARNING | Superlatives (`best`, `perfect`, `ultimate`) |
| QL-017 | WARNING | Nominalisations (`optimization` → `optimize`) |
| QL-018 | WARNING | Redundant phrases (`end result`, `past history`) |
| QL-019 | WARNING | Buzzwords (`leverage`, `synergy`, `paradigm`) |
| QL-020 | WARNING | Hedging language (`might`, `could possibly`) |
| QL-021 | ERROR | Sentence too long (> 35 words) |
| QL-022 | WARNING | Instruction body too long (> 500 lines) |
| QL-023 | WARNING | Missing `## Usage` or `## Overview` section |
| QL-024 | WARNING | Missing `## Examples` section |

Run `skillscan-lint rules` for the full list with descriptions.

### Graph rules (`GR-*`, requires `--graph`)

Graph rules analyze the **invocation graph** across a skills directory — which skills call which, what files they reference, and whether the dependency structure is sound.

| Rule | Severity | What it catches |
|------|----------|-----------------|
| GR-001 | ERROR | Cycle in skill invocation graph (A → B → A) |
| GR-002 | ERROR | Dangling reference (skill invokes a skill that doesn't exist) |
| GR-003 | WARNING | Orphan entry-point (invokes others but is never invoked — add `entry_point: true` if intentional) |
| GR-004 | WARNING | Hub skill (unusually high in-degree — single point of failure) |
| GR-005 | WARNING | Undocumented dependency (referenced skill has no `## Usage` or `## Overview` section) |
| GR-006 | WARNING | Broken intra-skill file reference (Markdown link points to a `.md` file that doesn't exist) |

Graph edges are resolved from three sources, in order of reliability:

1. **Front-matter keys** — `invoke:`, `calls:`, `depends_on:`, `uses:`, `requires:` with skill names or file paths
2. **Markdown links to `SKILL.md` files** — `[skill name](../other-skill/SKILL.md)`
3. **Path resolution** — front-matter values containing `/` or ending in `.md` are resolved relative to the skill file

Reference docs, README files, and other supporting `.md` files within a skill package are **not** treated as graph nodes — they are checked by GR-006 for broken links instead.

---

## CI Integration

### GitHub Actions

```yaml
- name: Lint skills
  run: |
    pip install skillscan-lint
    skillscan-lint scan ./skills/ --graph --format json > report.json
```

### Pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/kurtpayne/skillscan-lint
    rev: v0.3.0
    hooks:
      - id: skillscan-lint
        args: [--graph]
```

### Docker in CI

```yaml
- name: Lint skills
  run: |
    docker run --rm -v "${{ github.workspace }}:/work" \
      kurtpayne/skillscan-lint scan /work/skills/ --graph --format json \
      > skillscan-lint-report.json
```

---

## Skill Graph Example

Given a skills directory:

```
skills/
  data-fetcher/SKILL.md   (invoke: parser)
  parser/SKILL.md         (invoke: data-fetcher)   ← cycle!
  formatter/SKILL.md      (invoke: missing-skill)  ← dangling ref
```

Running `skillscan-lint scan ./skills/ --graph` will report:

```
GR-001  ERROR    Cycle detected: data-fetcher → parser → data-fetcher
GR-002  ERROR    Skill "formatter" references "missing-skill" which does not exist.
```

---

## Related

- **[skillscan-security](https://github.com/kurtpayne/skillscan-security)** — Security scanner for AI skills: prompt injection, IOC matching, malware detection, ML-based classifier
- **[skills.sh](https://skills.sh)** — Community registry of AI agent skills
- **[ClawHub](https://clawhub.ai)** — MCP skill marketplace

---

## License

Apache-2.0. See [LICENSE](LICENSE).
