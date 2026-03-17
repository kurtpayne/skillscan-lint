# skillscan-lint

Quality linter for AI agent skill files. Detects weasel words, ambiguity, readability issues, missing metadata, and skill invocation graph problems (cycles, dangling references).

## Install

```bash
pip install skillscan-lint
```

## Usage

```bash
skillscan-lint scan ./skills/
skillscan-lint scan SKILL.md --format json
skillscan-lint rules
```

## Rules

Run `skillscan-lint rules` to see all available rules.
