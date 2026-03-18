# skillscan-lint

**Quality linter for AI agent skill files.** Catches weasel words, ambiguous instructions, missing metadata, and skill graph problems (cycles, dangling references, broken file links) before they reach production.

Works with skills from [skills.sh](https://skills.sh), [ClawHub](https://clawhub.ai), and any `SKILL.md`-based skill package.

## Quick Start

```bash
# Lint a skills directory
docker run --rm -v "$PWD:/work" kurtpayne/skillscan-lint scan /work/skills/

# Include graph checks (cycles, dangling refs, broken links)
docker run --rm -v "$PWD:/work" kurtpayne/skillscan-lint scan /work/skills/ --graph

# JSON output for CI
docker run --rm -v "$PWD:/work" kurtpayne/skillscan-lint scan /work/skills/ --format json
```

## Example Output

```
SKILL.md
  QL-004  WARNING  Weasel intensifier "basically" weakens the instruction.
  QL-009  ERROR    Description too short (8 words). Minimum is 10.
  GR-002  ERROR    Skill "data-fetcher" references "parser" which does not exist.
  GR-006  WARNING  Broken file reference: "references/auth.md" does not exist.

1 error, 2 warnings
```

## Rules

**Quality rules (`QL-*`):** passive voice, weasel words, vague verbs, missing fields, name casing, TODO markers, superlatives, buzzwords, sentence length, and more.

**Graph rules (`GR-*`, `--graph` flag):** cycles, dangling references, orphan entry-points, hub skills, undocumented dependencies, and broken intra-skill file links.

Run `docker run --rm kurtpayne/skillscan-lint rules` to see all rules.

## CI Integration

```yaml
# GitHub Actions
- name: Lint skills
  run: |
    docker run --rm -v "${{ github.workspace }}:/work" \
      kurtpayne/skillscan-lint scan /work/skills/ --graph --format json \
      > skillscan-lint-report.json
```

## Related

- **[skillscan-security](https://hub.docker.com/r/kurtpayne/skillscan-security)** — Security scanner: prompt injection, IOC matching, malware detection
- **[skills.sh](https://skills.sh)** — Community registry of AI agent skills
- **[GitHub](https://github.com/kurtpayne/skillscan-lint)** — Source code and documentation
