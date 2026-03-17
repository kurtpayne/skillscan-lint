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

    MAX_WORDS = 35  # class-level default; overridden by [thresholds] max_sentence_length

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        max_words = self._threshold("max_sentence_length", self.MAX_WORDS)
        findings = []
        text = _get_all_text(parsed)
        sentences = re.split(r"[.!?]+", text)
        for sentence in sentences:
            words = sentence.split()
            if len(words) > max_words:
                findings.append(self._finding(
                    path,
                    f"Sentence has {len(words)} words (max {max_words}): "
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

    MIN_WORDS = 10  # class-level default; overridden by [thresholds] min_description_words

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        min_words = self._threshold("min_description_words", self.MIN_WORDS)
        desc = _get_description(parsed)
        if not desc:
            return [self._finding(path, "Description field is missing or empty.")]
        words = desc.split()
        if len(words) < min_words:
            return [self._finding(
                path,
                f"Description is only {len(words)} words (minimum {min_words}). "
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

    MAX_WORDS = 150  # class-level default; overridden by [thresholds] max_description_words

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        max_words = self._threshold("max_description_words", self.MAX_WORDS)
        desc = _get_description(parsed)
        words = desc.split()
        if len(words) > max_words:
            return [self._finding(
                path,
                f"Description is {len(words)} words (maximum {max_words}). "
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

# ---------------------------------------------------------------------------
# Extended weasel-word rules (QL-016 – QL-020)
# ---------------------------------------------------------------------------

# Superlatives that are unsubstantiated claims
WEASEL_SUPERLATIVES = re.compile(
    r"\b(best|fastest|most\s+\w+|greatest|perfect|ultimate|state[- ]of[- ]the[- ]art|"
    r"cutting[- ]edge|world[- ]class|industry[- ]leading|next[- ]gen(?:eration)?|"
    r"revolutionary|unprecedented|unmatched|unparalleled)\b",
    re.IGNORECASE,
)


@register
class WeaselSuperlativeRule(Rule):
    """QL-016 — Unsubstantiated superlatives make skill descriptions less credible."""

    rule_id = "QL-016"
    severity = Severity.WARNING
    category = Category.WEASEL
    description = "Unsubstantiated superlatives reduce credibility and add no information."
    suggestion_template = "Replace the superlative with a concrete, measurable claim or remove it."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            m = WEASEL_SUPERLATIVES.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Unsubstantiated superlative \"{m.group()}\" in: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# Nominalisation patterns — verb-derived nouns that obscure the action
_NOMINALISATIONS = re.compile(
    r"\b(utilization|utilisation|implementation|facilitation|"
    r"optimization|optimisation|leveraging|operationalization|"
    r"operationalisation|conceptualization|conceptualisation|"
    r"functionalization|instantiation)\b",
    re.IGNORECASE,
)


@register
class NominalisationRule(Rule):
    """QL-017 — Nominalisations (verb-derived nouns) obscure meaning."""

    rule_id = "QL-017"
    severity = Severity.INFO
    category = Category.READABILITY
    description = "Nominalisations obscure the action; prefer active verbs."
    suggestion_template = 'Replace the nominalisation with a direct verb (e.g. "use" instead of "utilization").'

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            m = _NOMINALISATIONS.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Nominalisation \"{m.group()}\" found; prefer an active verb: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# Redundant pairs — phrases where one word is sufficient
_REDUNDANT_PAIRS = re.compile(
    r"\b(each and every|first and foremost|null and void|"
    r"true and accurate|end result|future plans|past history|"
    r"past experience|advance planning|close proximity|"
    r"completely finish|completely eliminate|unexpected surprise|"
    r"added bonus|free gift|final outcome|basic fundamentals?|"
    r"brief summary|collaborate together|cooperate together|"
    r"join together|merge together|repeat again|revert back|"
    r"return back|sum total|total sum|absolutely essential|"
    r"absolutely necessary|completely full|completely empty)\b",
    re.IGNORECASE,
)


@register
class RedundantPhraseRule(Rule):
    """QL-018 — Redundant phrases add words without adding meaning."""

    rule_id = "QL-018"
    severity = Severity.INFO
    category = Category.READABILITY
    description = "Redundant phrase: one of the words is already implied by the other."
    suggestion_template = "Remove the redundant word (e.g. 'end result' -> 'result')."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            m = _REDUNDANT_PAIRS.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Redundant phrase \"{m.group()}\" in: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# Jargon / buzzwords that obscure meaning for LLM agents
_BUZZWORDS = re.compile(
    r"\b(synergy|synergize|synergistic|paradigm shift|disruptive|"
    r"circle back|move the needle|low[- ]hanging fruit|boil the ocean|"
    r"deep[- ]dive|ping\s+(?:me|us|them)|touch\s+base|"
    r"take\s+(?:this|it)\s+offline|at\s+the\s+end\s+of\s+the\s+day|"
    r"going\s+forward|proactive(?:ly)?|value[- ]add(?:ed)?|"
    r"game[- ]changer|thought\s+leader(?:ship)?)\b",
    re.IGNORECASE,
)


@register
class BuzzwordRule(Rule):
    """QL-019 — Business buzzwords reduce clarity for LLM agents."""

    rule_id = "QL-019"
    severity = Severity.WARNING
    category = Category.WEASEL
    description = "Business buzzword adds no actionable information for an LLM agent."
    suggestion_template = "Replace the buzzword with a plain-language description of the actual action or outcome."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            m = _BUZZWORDS.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Buzzword \"{m.group()}\" found: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# Weasel numbers — vague quantifiers that should be specific
_VAGUE_QUANTIFIERS = re.compile(
    r"\b(some|several|many|few|a\s+number\s+of|a\s+lot\s+of|"
    r"lots\s+of|a\s+bunch\s+of|a\s+variety\s+of|a\s+range\s+of|"
    r"a\s+series\s+of|a\s+set\s+of|various|numerous|countless|"
    r"multiple|most|most\s+of|the\s+majority\s+of|"
    r"a\s+significant\s+(?:number|amount|portion)\s+of|"
    r"a\s+large\s+(?:number|amount|portion)\s+of)\b",
    re.IGNORECASE,
)


@register
class VagueQuantifierRule(Rule):
    """QL-020 — Vague quantifiers should be replaced with specific values."""

    rule_id = "QL-020"
    severity = Severity.INFO
    category = Category.WEASEL
    description = "Vague quantifier provides no concrete information; use a specific value."
    suggestion_template = "Replace the vague quantifier with a specific number or range."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        desc = _get_description(parsed)
        for i, line in _iter_lines(desc):
            m = _VAGUE_QUANTIFIERS.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Vague quantifier \"{m.group()}\" in description: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


# ---------------------------------------------------------------------------
# Ambiguity / clarity rules (QL-021 – QL-025)
# ---------------------------------------------------------------------------

_ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")
_KNOWN_ACRONYMS = {
    "AI", "ML", "LLM", "API", "URL", "HTTP", "HTTPS", "JSON", "YAML",
    "CSV", "SQL", "PDF", "HTML", "CSS", "JS", "TS", "SDK", "CLI",
    "CI", "CD", "PR", "UI", "UX", "ID", "UUID", "UTC", "ISO",
    "REST", "RPC", "GRPC", "JWT", "SSH", "TLS", "SSL", "DNS",
    "AWS", "GCP", "GCS", "S3", "IAM", "VPC", "EC2", "ECS", "EKS",
    "CPU", "GPU", "RAM", "SSD", "HDD", "OS", "VM", "K8S", "K8",
    "NLP", "OCR", "RAG", "RLHF", "DPO", "SFT",
    "TODO", "FIXME", "NOTE", "WARN", "INFO", "DEBUG", "ERROR",
    "OK", "EOF", "EOL", "EOD", "EOM", "EOY", "ETA", "SLA", "SLO",
    "CRUD", "ORM", "MVC", "MVP", "POC", "RFC", "TBD", "WIP",
    "SARIF", "SBOM", "CVE", "CWE", "OWASP", "NIST", "SOC", "PCI",
}
_EXPANSION_RE = re.compile(r"\b\w[\w\s]+\s+\(([A-Z]{2,6})\)")


@register
class UndefinedAcronymRule(Rule):
    """QL-021 — Undefined acronyms reduce clarity for LLM agents."""

    rule_id = "QL-021"
    severity = Severity.WARNING
    category = Category.CLARITY
    description = "Acronym used without definition; define it on first use."
    suggestion_template = 'Define the acronym on first use: "Full Name (ACRONYM)".'

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        text = _get_all_text(parsed)
        defined = set(_EXPANSION_RE.findall(text))
        findings = []
        seen: set[str] = set()
        for i, line in _iter_lines(text):
            for m in _ACRONYM_RE.finditer(line):
                acr = m.group(1)
                if acr in _KNOWN_ACRONYMS or acr in defined or acr in seen:
                    continue
                seen.add(acr)
                findings.append(self._finding(
                    path,
                    f"Acronym \"{acr}\" used without definition: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


_DOUBLE_NEG_RE = re.compile(
    r"\b(not\s+un\w+|not\s+without|"
    r"cannot\s+(?:deny|disagree|dispute)|"
    r"never\s+not|hardly\s+(?:ever\s+)?not|"
    r"not\s+(?:impossible|unlikely|uncommon|unusual|unheard))\b",
    re.IGNORECASE,
)


@register
class DoubleNegativeRule(Rule):
    """QL-022 — Double negatives are harder to parse than positive statements."""

    rule_id = "QL-022"
    severity = Severity.WARNING
    category = Category.CLARITY
    description = "Double negative is harder to parse; rewrite as a positive statement."
    suggestion_template = 'Rewrite as a positive statement (e.g. "not uncommon" -> "common").'

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        findings = []
        text = _get_all_text(parsed)
        for i, line in _iter_lines(text):
            m = _DOUBLE_NEG_RE.search(line)
            if m:
                findings.append(self._finding(
                    path,
                    f"Double negative \"{m.group()}\" in: \"{line.strip()[:80]}\"",
                    line=i,
                ))
        return findings


@register
class MissingExamplesRule(Rule):
    """QL-023 — Skills without examples are harder for LLM agents to invoke correctly."""

    rule_id = "QL-023"
    severity = Severity.WARNING
    category = Category.COMPLETENESS
    description = "Skill has no examples; add an 'examples' section to guide LLM agents."
    suggestion_template = (
        "Add an 'examples:' list to the YAML front-matter, or a '## Examples' section "
        "in the Markdown body with at least one concrete usage example."
    )

    _EXAMPLES_HEADING = re.compile(r"^#{1,3}\s+examples?\b", re.IGNORECASE | re.MULTILINE)

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        has_yaml_examples = bool(parsed.get("examples"))
        has_md_examples = bool(self._EXAMPLES_HEADING.search(content))
        if not has_yaml_examples and not has_md_examples:
            return [self._finding(
                path,
                "No 'examples' section found. Add examples to help LLM agents invoke this skill correctly.",
            )]
        return []


@register
class MissingTagsRule(Rule):
    """QL-024 — Skills without tags are harder to discover and categorise."""

    rule_id = "QL-024"
    severity = Severity.INFO
    category = Category.COMPLETENESS
    description = "Skill has no tags; add at least one tag for discoverability."
    suggestion_template = "Add a 'tags:' list to the YAML front-matter (e.g. tags: [search, web])."

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        tags = parsed.get("tags")
        if not tags or (isinstance(tags, (list, tuple)) and len(tags) == 0):
            return [self._finding(
                path,
                "No 'tags' field found. Add tags to improve discoverability.",
            )]
        return []


_IMPERATIVE_STARTERS = re.compile(
    r"^(This\s+skill|The\s+skill|This\s+tool|The\s+tool|"
    r"It\s+(?:will|can|should|does|is)|"
    r"A\s+skill\s+that|An?\s+\w+\s+that)\b",
    re.IGNORECASE,
)


@register
class ImperativeMoodRule(Rule):
    """QL-025 — Skill descriptions should start with an imperative verb."""

    rule_id = "QL-025"
    severity = Severity.INFO
    category = Category.READABILITY
    description = "Description should start with an imperative verb, not 'This skill' or 'It will'."
    suggestion_template = (
        'Start the description with an imperative verb, e.g. "Fetches weather data..." '
        'instead of "This skill fetches weather data...".'
    )

    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list:
        desc = _get_description(parsed).strip()
        if not desc:
            return []
        first_sentence = re.split(r"[.!?]", desc)[0].strip()
        if _IMPERATIVE_STARTERS.match(first_sentence):
            return [self._finding(
                path,
                f"Description starts with a weak opener: \"{first_sentence[:80]}\". "
                "Use an imperative verb instead.",
            )]
        return []
