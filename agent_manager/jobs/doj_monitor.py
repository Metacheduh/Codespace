"""
DOJ Press Release Monitor Job

Fetches DOJ news pages, extracts articles, and matches against
configured keywords.  Keyword matching is deterministic string
comparison — no LLM.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any
from urllib.request import Request, urlopen

from agent_manager.jobs.base import BaseJob
from agent_manager.models import Database

logger = logging.getLogger(__name__)


class DOJMonitorJob(BaseJob):
    name = "doj_monitor"

    def __init__(self, config: dict[str, Any], db: Database) -> None:
        super().__init__(config, db)
        self.sources = config.get("sources", [])
        self.keywords: list[str] = [k.lower() for k in config.get("keywords", [])]

    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        for source in self.sources:
            url = source["url"]
            logger.info("Fetching DOJ articles from %s", url)
            html = self._fetch(url)
            content_hash = self.content_hash(html)

            conn.execute(
                "INSERT INTO snapshots (source_name, job_run_id, url, content_hash, raw_content) "
                "VALUES (?, ?, ?, ?, ?)",
                (source["name"], run_id, url, content_hash, html),
            )

            articles = self._extract_articles(html)
            for article in articles:
                self._process_article(conn, run_id, article, "doj")

    def _fetch(self, url: str) -> str:
        req = Request(url, headers={"User-Agent": "AgentManager/0.1"})
        with urlopen(req, timeout=self.config.get("timeout_seconds", 180)) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")

    def _extract_articles(self, html: str) -> list[dict[str, str]]:
        """Deterministic HTML parsing for article blocks."""
        articles: list[dict[str, str]] = []
        # Extract <a> tags with titles and hrefs
        pattern = re.findall(
            r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for href, title_raw in pattern:
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if title and len(title) > 10:
                articles.append({"title": title, "url": href})
        return articles

    def _process_article(
        self, conn: sqlite3.Connection, run_id: int, article: dict[str, str], source: str
    ) -> None:
        title = article["title"]
        url = article["url"]
        content_hash = self.content_hash(title + url)

        # Deterministic keyword matching (case-insensitive string search)
        hits = [kw for kw in self.keywords if kw in title.lower()]
        keyword_hits_json = json.dumps(hits) if hits else None

        try:
            conn.execute(
                "INSERT INTO articles "
                "(job_run_id, source, title, url, content_hash, keyword_hits) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, source, title, url, content_hash, keyword_hits_json),
            )
            if hits:
                logger.info("Keyword match in %r: %s", title, hits)
        except sqlite3.IntegrityError:
            # Article URL already recorded — skip
            pass
