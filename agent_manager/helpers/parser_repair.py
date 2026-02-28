"""
Parser Repair Assistant  (optional, human-in-the-loop).

Used ONLY when parsing fails after HTML structure changes on
source websites.  Suggests updated CSS selectors or parsing rules.

CONSTRAINTS:
  - Output: suggested selector updates / parsing rules ONLY.
  - Requires EXPLICIT USER APPROVAL before any code changes are applied.
  - Never modifies code or config autonomously.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepairSuggestion:
    """A suggested parsing rule update (requires human approval)."""
    source_name: str
    selector_key: str
    old_selector: str
    suggested_selector: str
    confidence: str  # "low", "medium", "high" (advisory only)
    reasoning: str


class ParserRepairAssistant:
    """Suggest parsing rule repairs when scraping fails.

    All suggestions require explicit human approval.
    This module NEVER modifies config or code automatically.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.enabled = config.get("enabled", False)
        self.requires_human_approval = config.get("requires_human_approval", True)
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 2048)

    def suggest_repair(
        self,
        source_name: str,
        selector_key: str,
        old_selector: str,
        failed_html_sample: str,
        llm_callable: Any | None = None,
    ) -> RepairSuggestion | None:
        """Generate a repair suggestion for a failed selector.

        Args:
            source_name: Name of the source (e.g., "fund_balance").
            selector_key: Config key for the selector (e.g., "balance").
            old_selector: The CSS selector that no longer works.
            failed_html_sample: A sample of the HTML that failed to parse.
            llm_callable: Optional callable(prompt: str) -> str.

        Returns:
            A RepairSuggestion if one can be generated, or None.
            The suggestion MUST be reviewed and approved by a human
            before being applied.
        """
        if not self.enabled:
            logger.debug("Parser repair assistant is disabled")
            return None

        if llm_callable is None:
            logger.info("No LLM callable provided for parser repair")
            return self._deterministic_suggestion(source_name, selector_key, old_selector)

        prompt = (
            f"The CSS selector '{old_selector}' no longer matches any elements "
            f"on the {source_name} page. Here is a sample of the current HTML:\n\n"
            f"```html\n{failed_html_sample[:3000]}\n```\n\n"
            f"Suggest an updated CSS selector that would match the same type of "
            f"content. Return ONLY the new selector string, nothing else."
        )

        try:
            suggested = llm_callable(prompt).strip().strip('"').strip("'")
            return RepairSuggestion(
                source_name=source_name,
                selector_key=selector_key,
                old_selector=old_selector,
                suggested_selector=suggested,
                confidence="medium",
                reasoning=f"LLM-suggested replacement for failed selector on {source_name}",
            )
        except Exception as exc:
            logger.warning("LLM parser repair failed: %s", exc)
            return self._deterministic_suggestion(source_name, selector_key, old_selector)

    @staticmethod
    def _deterministic_suggestion(
        source_name: str, selector_key: str, old_selector: str
    ) -> RepairSuggestion:
        """Provide a fallback suggestion without LLM."""
        return RepairSuggestion(
            source_name=source_name,
            selector_key=selector_key,
            old_selector=old_selector,
            suggested_selector=old_selector,  # no change — needs human inspection
            confidence="low",
            reasoning=(
                "Automatic repair could not determine a replacement. "
                "Manual inspection of the source HTML is required."
            ),
        )

    def apply_suggestion(self, suggestion: RepairSuggestion, approved: bool) -> bool:
        """Apply a repair suggestion ONLY if explicitly approved by a human.

        Returns True if the suggestion was approved and would be applied.
        The actual config update must be performed by the caller.
        """
        if not self.requires_human_approval:
            logger.warning(
                "requires_human_approval is False — this violates the "
                "deterministic orchestration requirement. Refusing to auto-apply."
            )
            return False

        if not approved:
            logger.info(
                "Repair suggestion for %s/%s was NOT approved by user",
                suggestion.source_name,
                suggestion.selector_key,
            )
            return False

        logger.info(
            "Repair suggestion APPROVED: %s/%s: %r → %r",
            suggestion.source_name,
            suggestion.selector_key,
            suggestion.old_selector,
            suggestion.suggested_selector,
        )
        return True
