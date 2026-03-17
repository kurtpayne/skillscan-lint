"""Core data models for skillscan-lint."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    READABILITY = "readability"
    CLARITY = "clarity"
    STRUCTURE = "structure"
    GRAPH = "graph"
    WEASEL = "weasel"
    COMPLETENESS = "completeness"


@dataclass
class LintFinding:
    rule_id: str
    severity: Severity
    category: Category
    message: str
    path: Path
    line: int | None = None
    column: int | None = None
    context: str | None = None
    suggestion: str | None = None

    def __str__(self) -> str:
        loc = f":{self.line}" if self.line else ""
        return f"[{self.severity.value.upper()}] {self.path}{loc} — {self.rule_id}: {self.message}"


@dataclass
class LintResult:
    path: Path
    findings: list[LintFinding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def infos(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == Severity.INFO]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ScanSummary:
    results: list[LintResult]
    total_files: int
    skipped_files: int

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.results)

    @property
    def total_errors(self) -> int:
        return sum(len(r.errors) for r in self.results)

    @property
    def total_warnings(self) -> int:
        return sum(len(r.warnings) for r in self.results)

    @property
    def passed(self) -> bool:
        return self.total_errors == 0
