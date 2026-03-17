# Vale Integration for skillscan-lint

This directory contains a [Vale](https://vale.sh) prose linter configuration that mirrors the `skillscan-lint` QL rule set. It enables **inline editor feedback** (VS Code, Neovim, Emacs) and **CI prose checks** without running the full Python linter.

## Rule coverage

| Vale style file | skillscan-lint rule | Category | Level |
|---|---|---|---|
| `SkillScan/WeaselIntensifiers.yml` | QL-004 | Weasel | warning |
| `SkillScan/WeaselHedges.yml` | QL-005 | Weasel | suggestion |
| `SkillScan/WeaselFillers.yml` | QL-006 | Weasel | warning |
| `SkillScan/VagueActions.yml` | QL-008 | Clarity | warning |
| `SkillScan/PassiveVoice.yml` | QL-003 | Readability | suggestion |
| `SkillScan/Superlatives.yml` | QL-016 | Weasel | warning |
| `SkillScan/Nominalisations.yml` | QL-017 | Readability | suggestion |
| `SkillScan/RedundantPhrases.yml` | QL-018 | Readability | suggestion |
| `SkillScan/Buzzwords.yml` | QL-019 | Weasel | warning |
| `SkillScan/DoubleNegatives.yml` | QL-022 | Clarity | warning |

Rules that require structural analysis (graph integrity, missing fields, word count) are not expressible as Vale styles and remain exclusive to `skillscan-lint`.

## Installation

### 1. Install Vale

```bash
# macOS
brew install vale

# Windows
choco install vale

# Linux (snap)
sudo snap install vale

# Linux (binary)
curl -sfL https://install.vale.sh | sh
```

### 2. Sync styles

From the repository root:

```bash
vale sync
```

This downloads any referenced external packages. The `SkillScan` styles are local and do not require a download.

### 3. Lint a skill file

```bash
# Single file
vale path/to/SKILL.md

# All skill files in a directory
vale path/to/skills/

# Respect .vale.ini from the repo root
vale --config .vale.ini path/to/SKILL.md
```

## VS Code integration

1. Install the [Vale VSCode](https://marketplace.visualstudio.com/items?itemName=ChrisChinchilla.vale-vscode) extension.
2. Set `"vale.valeCLI.config": "${workspaceFolder}/.vale.ini"` in your VS Code settings.
3. Underlines appear inline as you type.

## CI integration

Add a Vale check step to your GitHub Actions workflow:

```yaml
- name: Install Vale
  uses: errata-ai/vale-action@reviewdog
  with:
    files: '**/*.md'
    vale_flags: '--config .vale.ini'
```

Or with the Vale CLI directly:

```yaml
- name: Lint skill files with Vale
  run: |
    curl -sfL https://install.vale.sh | sh
    vale --config .vale.ini --output line skills/
```

## Relationship to skillscan-lint

Vale and `skillscan-lint` are **complementary**, not redundant:

| Capability | Vale | skillscan-lint |
|---|---|---|
| Inline editor feedback | Yes | No |
| Weasel words / buzzwords | Yes | Yes |
| Passive voice | Yes | Yes |
| Graph integrity (cycles, dangling refs) | No | Yes |
| Missing required fields | No | Yes |
| Word count bounds | No | Yes |
| Undefined acronyms | No | Yes |
| YAML front-matter parsing | No | Yes |
| CI JSON / SARIF output | No | Yes |

The recommended workflow is to use Vale for **fast editor feedback** during authoring and `skillscan-lint` for **authoritative CI gating**.
