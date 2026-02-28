"""
Classification Helper  (optional, advisory only).

Tags DOJ/OFAC articles with advisory labels such as
"likely sanctions/IEEPA" or "not relevant".

CONSTRAINTS:
  - Tags are NON-AUTHORITATIVE.
  - Tags MUST NOT affect confirmed status, trigger alerts,
    or influence scheduling decisions.
  - Tags are written to the `advisory_tags` column only.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from agent_manager.models import Database

logger = logging.getLogger(__name__)

# Deterministic keyword-to-tag mapping (no LLM needed for basic tagging)
KEYWORD_TAG_MAP: dict[str, str] = {
    "sanctions": "likely-sanctions",
    "ieepa": "likely-IEEPA",
    "terrorism": "likely-terrorism-related",
    "restitution": "likely-restitution",
    "forfeiture": "likely-forfeiture",
    "victim compensation": "likely-victim-compensation",
    "narcotics": "likely-narcotics",
    "cyber": "likely-cyber",
    "wmd": "likely-WMD",
}


class ClassificationHelper:
    """Tag articles with advisory (non-authoritative) classifications.

    Can optionally use an LLM for richer tagging, but falls back to
    deterministic keyword mapping.
    """

    def __init__(self, config: dict[str, Any], db: Database) -> None:
        self.enabled = config.get("enabled", False)
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 256)
        self.db = db

    def classify_untagged_articles(
        self,
        conn: sqlite3.Connection,
        llm_callable: Any | None = None,
    ) -> int:
        """Tag articles that don't yet have advisory_tags.

        Returns the number of articles tagged.
        """
        if not self.enabled:
            logger.debug("Classification helper is disabled")
            return 0

        rows = conn.execute(
            "SELECT id, title, keyword_hits FROM articles WHERE advisory_tags IS NULL"
        ).fetchall()

        count = 0
        for row in rows:
            tags = self._classify_article(
                row["title"],
                row["keyword_hits"],
                llm_callable,
            )
            # Write ONLY to advisory_tags column (non-authoritative)
            conn.execute(
                "UPDATE articles SET advisory_tags = ? WHERE id = ?",
                (json.dumps(tags), row["id"]),
            )
            count += 1

        logger.info("Tagged %d article(s) with advisory classifications", count)
        return count

    def _classify_article(
        self,
        title: str,
        keyword_hits_json: str | None,
        llm_callable: Any | None,
    ) -> list[str]:
        """Classify a single article, returning advisory tags."""
        # Always start with deterministic keyword-based tags
        tags = self._deterministic_tags(title, keyword_hits_json)

        # Optionally enhance with LLM (advisory only)
        if llm_callable is not None:
            try:
                prompt = (
                    f"Classify this article title into one or more categories "
                    f"(sanctions, IEEPA, terrorism, restitution, forfeiture, "
                    f"victim-compensation, narcotics, cyber, not-relevant).\n"
                    f"Title: {title}\n"
                    f"Return ONLY a JSON list of tag strings."
                )
                result = llm_callable(prompt)
                llm_tags = json.loads(result)
                if isinstance(llm_tags, list):
                    # Merge (union) with deterministic tags
                    tags = list(set(tags) | set(str(t) for t in llm_tags))
            except Exception as exc:
                logger.warning("LLM classification failed for %r: %s", title, exc)

        if not tags:
            tags = ["unclassified"]

        return tags

    @staticmethod
    def _deterministic_tags(title: str, keyword_hits_json: str | None) -> list[str]:
        """Generate tags from deterministic keyword mapping."""
        tags: list[str] = []
        title_lower = title.lower()

        for keyword, tag in KEYWORD_TAG_MAP.items():
            if keyword in title_lower:
                tags.append(tag)

        # Also check the already-matched keywords from the scraper
        if keyword_hits_json:
            try:
                hits = json.loads(keyword_hits_json)
                for hit in hits:
                    mapped = KEYWORD_TAG_MAP.get(hit.lower())
                    if mapped and mapped not in tags:
                        tags.append(mapped)
            except (json.JSONDecodeError, TypeError):
                pass

        return tags
