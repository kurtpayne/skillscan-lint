"""Base rule class and rule registry for skillscan-lint."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from skillscan_lint.models import Category, LintFinding, Severity

if TYPE_CHECKING:
    from skillscan_lint.config import ThresholdsConfig


class Rule(ABC):
    """Base class for all lint rules."""

    rule_id: str
    severity: Severity
    category: Category
    description: str
    suggestion_template: str | None = None

    # Injected at instantiation time from .skillscan-lint.toml [thresholds].
    # Rules that use numeric thresholds should read them via _threshold() helper.
    thresholds: ThresholdsConfig | None = None

    @abstractmethod
    def check(self, path: Path, content: str, parsed: dict[str, Any]) -> list[LintFinding]:
        """Run the rule against a parsed skill file. Return a list of findings."""
        ...

    def _threshold(self, name: str, default: int) -> int:
        """Return a threshold value from config if available, else the class default."""
        if self.thresholds is not None:
            return int(getattr(self.thresholds, name, default))
        return default

    def _finding(
        self,
        path: Path,
        message: str,
        line: int | None = None,
        context: str | None = None,
        suggestion: str | None = None,
    ) -> LintFinding:
        return LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            category=self.category,
            message=message,
            path=path,
            line=line,
            context=context,
            suggestion=suggestion or self.suggestion_template,
        )


# Global rule registry
_REGISTRY: dict[str, type[Rule]] = {}


def register(cls: type[Rule]) -> type[Rule]:
    """Decorator to register a rule class."""
    _REGISTRY[cls.rule_id] = cls
    return cls


def get_all_rules(thresholds: ThresholdsConfig | None = None) -> list[Rule]:
    """Return instantiated instances of all registered rules.

    If *thresholds* is provided, it is injected into each rule instance so
    that threshold-sensitive rules (word count, sentence length) use the
    values from .skillscan-lint.toml instead of their class-level defaults.
    """
    rules = [cls() for cls in _REGISTRY.values()]
    if thresholds is not None:
        for rule in rules:
            rule.thresholds = thresholds
    return rules


def get_rule(rule_id: str) -> Rule | None:
    cls = _REGISTRY.get(rule_id)
    return cls() if cls else None
