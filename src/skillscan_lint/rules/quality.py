"""NLP quality rules for skillscan-lint.

Design philosophy: Every rule targets a specific, measurable quality signal
in AI agent skill files. Rules are conservative — they flag genuine issues,
not stylistic preferences.

Categories covered:
- Readability: Flesch-Kincaid grade level, sentence length, passive voice
- Weasel words: vague intensifiers, hedge words, filler phrases
- Ambiguity: pronouns without antecedents, undefined "it/they/this"
- Structure: missing required sections, word count bounds
- Completeness: missing description, empty steps, no examples
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import textstat
    HAS_TEXTSTAT = True
except ImportError:
    HAS_TEXTSTAT = False

from skillscan_lint.models import Category, Severity
from skillscan_lint.rules.base import Rule, register

# ---------------------------------------------------------------------------
# Weasel word lists
# ---------------------------------------------------------------------------

WEASEL_INTENSIFIERS = [
    r"\bvery\b", r"\bextremely\b", r"\bincredibly\b", r"\bquite\b",
    r"\brather\b", r"\bfairly\b", r"\bsomewhat\b", r"\bpretty\b",
    r"\breally\b", r"\bbasically\b", r"\bessentially\b", r"\bactually\b",
    r"\bliterally\b", r"\btotally\b", r"\babsolutely\b",
]

WEASEL_HEDGES = [
    r"\bsomehow\b", r"\bseems?\b", r"\bappears?\b", r"\bapparently\b",
    r"\bpossibly\b", r"\bperhaps\b", r"\bmaybe\b", r"\bmight\b",
    r"\bcould\b", r"\bwould\b", r"\bshould\b", r"\bgenerally\b",
    r"\busually\b", r"\btypically\b", r"\bnormally\b", r"\boften\b",
]

WEASEL_FILLERS = [
    r"\bin order to\b", r"\bdue to the fact that\b", r"\bat this point in time\b",
    r"\bfor the purpose of\b", r"\bin the event that\b", r"\bit is important to note\b",
    r"\bit should be noted\b", r"\bplease note\b", r"\bkindly\b",
    r"\bfeel free to\b", r"\bdon't hesitate\b",
]

PASSIVE_VOICE_PATTERN = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+([\w]+ed|[\w]+en)\b",
    re.IGNORECASE,
)

AMBIGUOUS_PRONOUNS = re.compile(
    r"\b(it|they|them|their|this|that|these|those)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helper: extract text fields from parsed SKILL.md front-matter + body
# ---------------------------------------------------------------------------

def _get_description(parsed: dict[str, Any]) -> str:
    return str(parsed.get("description", ""))


def _get_body(parsed: dict[str, Any]) -> str:
    return str(parsed.get("_body", ""))


def _get_all_text(parsed: dict[str, Any]) -> str:
    parts = []
    for key in ("description", "usage", "notes", "_body"):
        val = parsed.get(key)
        if val:
            parts.append(str(val))
    return " ".join(parts)


def _iter_lines(text: str):
    for i, line in enumerate(text.splitlines(), start=1):
        yield i, line


# ---------------------------------------------------------------------------
# Readability rules
# ---------------------------------------------------------------------------

@register
class ReadingLevelRule(Rule):
    rule_id = "QL-001"
    severity = Severity.WARNING
    category = Category.READABILITY
    description = "Description reading level should not exceed grade 12 (Flesch-Kincaid)."
    suggestion_template = "Simplify sentences: use shorter words and break up long sentences."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        if not HAS_TEXTSTAT:
            return []
        text = _get_description(parsed)
        if len(text.split()) < 20:
            return []
        grade = textstat.flesch_kincaid_grade(text)
        if grade > 12:
            return [self._finding(
                path,
                f"Description reading level is grade {grade:.1f} (target ≤ 12). "
                "Consider simplifying the language.",
            )]
        return []


@register
class LongSentenceRule(Rule):
    rule_id = "QL-002"
    severity = Severity.WARNING
    category = Category.READABILITY
    description = "Sentences longer than 35 words are hard to parse."
    suggestion_template = "Break the sentence into two shorter ones."

    MAX_WORDS = 35

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        sentences = re.split(r"[.!?]+", text)
        for sentence in sentences:
            words = sentence.split()
            if len(words) > self.MAX_WORDS:
                findings.append(self._finding(
                    path,
                    f"Sentence has {len(words)} words (max {self.MAX_WORDS}): "
                    f'"{sentence.strip()[:80]}…"',
                    suggestion=self.suggestion_template,
                ))
        return findings


@register
class PassiveVoiceRule(Rule):
    rule_id = "QL-003"
    severity = Severity.INFO
    category = Category.READABILITY
    description = "Passive voice reduces clarity in skill descriptions."
    suggestion_template = "Rewrite using active voice: 'The skill does X' instead of 'X is done by the skill'."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            if PASSIVE_VOICE_PATTERN.search(line):
                findings.append(self._finding(
                    path,
                    f"Possible passive voice detected: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# ---------------------------------------------------------------------------
# Weasel word rules
# ---------------------------------------------------------------------------

@register
class WeaselIntensifierRule(Rule):
    rule_id = "QL-004"
    severity = Severity.WARNING
    category = Category.WEASEL
    description = "Vague intensifiers (very, extremely, basically, etc.) weaken precision."
    suggestion_template = "Remove the intensifier or replace with a specific, measurable claim."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            for pattern in WEASEL_INTENSIFIERS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    findings.append(self._finding(
                        path,
                        f"Weasel intensifier \"{m.group()}\" found: \"{line.strip()[:80]}\"",
                        line=i,
                    ))
                    break  # one finding per line
        return findings


@register
class WeaselHedgeRule(Rule):
    rule_id = "QL-005"
    severity = Severity.INFO
    category = Category.WEASEL
    description = "Hedge words (seems, perhaps, might, typically, etc.) reduce confidence and precision."
    suggestion_template = "Replace with a definitive statement or specify the condition explicitly."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_description(parsed)
        for i, line in _iter_lines(text):
            for pattern in WEASEL_HEDGES:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    findings.append(self._finding(
                        path,
                        f"Hedge word \"{m.group()}\" found in description: \"{line.strip()[:80]}\"",
                        line=i,
                    ))
                    break
        return findings


@register
class WeaselFillerRule(Rule):
    rule_id = "QL-006"
    severity = Severity.WARNING
    category = Category.WEASEL
    description = "Filler phrases (in order to, please note, feel free to, etc.) add noise."
    suggestion_template = "Remove the filler phrase and state the intent directly."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            for pattern in WEASEL_FILLERS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    findings.append(self._finding(
                        path,
                        f"Filler phrase \"{m.group()}\" found: \"{line.strip()[:80]}\"",
                        line=i,
                    ))
                    break
        return findings


# ---------------------------------------------------------------------------
# Ambiguity rules
# ---------------------------------------------------------------------------

@register
class AmbiguousPronounRule(Rule):
    rule_id = "QL-007"
    severity = Severity.WARNING
    category = Category.CLARITY
    description = "Ambiguous pronouns (it, they, this, that) without a clear antecedent confuse LLM agents."
    suggestion_template = "Replace the pronoun with the explicit noun it refers to."

    # Only flag in description/usage, not in body markdown prose
    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_description(parsed)
        sentences = re.split(r"[.!?]+", text)
        for sentence in sentences:
            words = sentence.split()
            # Flag if sentence starts with an ambiguous pronoun (no prior context)
            if words and AMBIGUOUS_PRONOUNS.match(words[0]):
                findings.append(self._finding(
                    path,
                    f"Sentence starts with ambiguous pronoun \"{words[0]}\": "
                    f"\"{sentence.strip()[:80]}\"",
                    suggestion=self.suggestion_template,
                ))
        return findings


@register
class VagueActionRule(Rule):
    rule_id = "QL-008"
    severity = Severity.WARNING
    category = Category.CLARITY
    description = "Vague action verbs (handle, process, manage, deal with) lack specificity."
    suggestion_template = "Replace with a precise verb: fetch, parse, validate, transform, store, etc."

    VAGUE_VERBS = re.compile(
        r"\b(handle[sd]?|handles|handling|process(?:es|ed|ing)?|manage[sd]?|manages|managing"
        r"|deal(?:s|t|ing)?\s+with|take\s+care\s+of|work(?:s|ed|ing)?\s+with)\b",
        re.IGNORECASE,
    )

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_description(parsed)
        for i, line in _iter_lines(text):
            m = self.VAGUE_VERBS.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Vague action verb \"{m.group()}\" in description: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# ---------------------------------------------------------------------------
# Word count / structure rules
# ---------------------------------------------------------------------------

@register
class DescriptionTooShortRule(Rule):
    rule_id = "QL-009"
    severity = Severity.ERROR
    category = Category.COMPLETENESS
    description = "Description must be at least 10 words to be meaningful to an LLM agent."
    suggestion_template = "Expand the description to clearly state what the skill does, its inputs, and its outputs."

    MIN_WORDS = 10

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        desc = _get_description(parsed)
        if not desc:
            return [self._finding(path, "Description field is missing or empty.")]
        words = desc.split()
        if len(words) < self.MIN_WORDS:
            return [self._finding(
                path,
                f"Description is only {len(words)} words (minimum {self.MIN_WORDS}). "
                "Add more detail about what the skill does.",
            )]
        return []


@register
class DescriptionTooLongRule(Rule):
    rule_id = "QL-010"
    severity = Severity.WARNING
    category = Category.READABILITY
    description = "Descriptions over 150 words may exceed LLM context windows or reduce focus."
    suggestion_template = "Move detailed implementation notes to a 'notes' or 'details' section."

    MAX_WORDS = 150

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        desc = _get_description(parsed)
        words = desc.split()
        if len(words) > self.MAX_WORDS:
            return [self._finding(
                path,
                f"Description is {len(words)} words (maximum {self.MAX_WORDS}). "
                "Consider moving detail to a notes section.",
            )]
        return []


@register
class MissingDescriptionRule(Rule):
    rule_id = "QL-011"
    severity = Severity.ERROR
    category = Category.COMPLETENESS
    description = "Skill file must have a 'description' field in YAML front-matter."
    suggestion_template = "Add a 'description:' field to the YAML front-matter."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        if not parsed.get("description"):
            return [self._finding(path, "Missing required 'description' field in front-matter.")]
        return []


@register
class MissingNameRule(Rule):
    rule_id = "QL-012"
    severity = Severity.ERROR
    category = Category.COMPLETENESS
    description = "Skill file must have a 'name' field in YAML front-matter."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        if not parsed.get("name"):
            return [self._finding(path, "Missing required 'name' field in front-matter.")]
        return []


@register
class NameCasingRule(Rule):
    rule_id = "QL-013"
    severity = Severity.WARNING
    category = Category.STRUCTURE
    description = "Skill name should use snake_case or kebab-case, not spaces or CamelCase."
    suggestion_template = "Use snake_case (my_skill) or kebab-case (my-skill) for the skill name."

    VALID_NAME = re.compile(r"^[a-z][a-z0-9_\-]*$")

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        name = str(parsed.get("name", ""))
        if name and not self.VALID_NAME.match(name):
            return [self._finding(
                path,
                f"Skill name \"{name}\" should be snake_case or kebab-case.",
            )]
        return []


@register
class MissingVersionRule(Rule):
    rule_id = "QL-014"
    severity = Severity.WARNING
    category = Category.COMPLETENESS
    description = "Skill file should declare a 'version' for reproducibility."
    suggestion_template = "Add 'version: \"1.0.0\"' to the YAML front-matter."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        if not parsed.get("version"):
            return [self._finding(path, "Missing 'version' field. Add a semantic version for reproducibility.")]
        return []


@register
class TodoInDescriptionRule(Rule):
    rule_id = "QL-015"
    severity = Severity.ERROR
    category = Category.COMPLETENESS
    description = "TODO/FIXME markers in skill content indicate incomplete work."

    TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX|PLACEHOLDER)\b", re.IGNORECASE)

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        for i, line in _iter_lines(content):
            m = self.TODO_PATTERN.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Incomplete marker \"{m.group()}\" found: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings
