"""
USVSST Scraper Job

Fetches fund-balance and qualifying-cases pages from the USVSST website.
Parses numeric balances and case listings.
Writes confirmed data to SQLite.

Deposit confirmation is derived ONLY from USVSST postings —
never from LLM inference.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from agent_manager.helpers.circuit_breaker import CircuitBreakerManager
from agent_manager.jobs.base import BaseJob
from agent_manager.models import Database

logger = logging.getLogger(__name__)


class USVSSTScraperJob(BaseJob):
    name = "usvsst_scraper"

    def __init__(
        self,
        config: dict[str, Any],
        db: Database,
        circuit_breakers: CircuitBreakerManager | None = None,
    ) -> None:
        super().__init__(config, db)
        self.sources = config.get("sources", [])
        self.circuit_breakers = circuit_breakers

    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        for source in self.sources:
            source_name = source["name"]
            url = source["url"]
            logger.info("Fetching %s from %s", source_name, url)

            # Check circuit breaker before fetching
            if self.circuit_breakers and not self.circuit_breakers.allow_request(url):
                logger.warning("Circuit breaker OPEN for %s — skipping", url)
                continue

            try:
                html = self._fetch(url)
                if self.circuit_breakers:
                    self.circuit_breakers.record_success(url)
            except Exception as e:
                if self.circuit_breakers:
                    self.circuit_breakers.record_failure(url)
                raise

            content_hash = self.content_hash(html)

            # Store raw snapshot
            conn.execute(
                "INSERT INTO snapshots (source_name, job_run_id, url, content_hash, raw_content) "
                "VALUES (?, ?, ?, ?, ?)",
                (source_name, run_id, url, content_hash, html),
            )

            # Check if content changed since last snapshot
            prev = conn.execute(
                "SELECT content_hash FROM snapshots "
                "WHERE source_name = ? AND id < (SELECT MAX(id) FROM snapshots WHERE source_name = ?) "
                "ORDER BY id DESC LIMIT 1",
                (source_name, source_name),
            ).fetchone()

            if prev and prev["content_hash"] == content_hash:
                logger.info("No change detected for %s", source_name)
                continue

            selectors = source.get("selectors", {})
            if source_name == "fund_balance":
                self._parse_fund_balance(conn, run_id, html, selectors)
            elif source_name == "qualifying_cases":
                self._parse_qualifying_cases(conn, run_id, html, selectors)

    def _fetch(self, url: str) -> str:
        req = Request(url, headers={"User-Agent": "AgentManager/0.1"})
        with urlopen(req, timeout=self.config.get("timeout_seconds", 120)) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")

    def _parse_fund_balance(
        self, conn: sqlite3.Connection, run_id: int, html: str, selectors: dict
    ) -> None:
        """Extract dollar amounts from the fund balance page using CSS selectors.

        Uses deterministic BeautifulSoup parsing — no LLM.
        """
        soup = BeautifulSoup(html, "html.parser")
        selector = selectors.get("balance")
        if not selector:
            logger.warning("No 'balance' selector configured")
            return

        elements = soup.select(selector)
        if not elements:
            logger.warning("No elements matched selector: %s", selector)
            return

        for element in elements:
            text = element.get_text(strip=True)
            # Match dollar amounts like $1,234,567.89
            match = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
            if not match:
                continue
            raw = match.group(0)
            cleaned = raw.replace("$", "").replace(",", "")
            try:
                amount = float(cleaned)
            except ValueError:
                continue
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount, raw_text) VALUES (?, ?, ?)",
                (run_id, amount, raw),
            )
            logger.info("Recorded fund balance: %s (%.2f)", raw, amount)

    def _parse_qualifying_cases(
        self, conn: sqlite3.Connection, run_id: int, html: str, selectors: dict
    ) -> None:
        """Extract qualifying case names from the page using CSS selectors.

        Uses deterministic BeautifulSoup parsing — no LLM.
        """
        soup = BeautifulSoup(html, "html.parser")
        selector = selectors.get("case_rows")
        if not selector:
            logger.warning("No 'case_rows' selector configured")
            return

        rows = soup.select(selector)
        if not rows:
            logger.warning("No rows matched selector: %s", selector)
            return

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            case_name = cells[0].get_text(strip=True)
            details = cells[1].get_text(strip=True)
            if not case_name:
                continue
            # UPSERT: only insert if not already known
            conn.execute(
                "INSERT OR IGNORE INTO qualifying_cases (job_run_id, case_name, case_details) "
                "VALUES (?, ?, ?)",
                (run_id, case_name, details),
            )
            logger.info("Recorded qualifying case: %s", case_name)

    def _detect_deposits(self, conn: sqlite3.Connection, run_id: int) -> None:
        """Detect new deposits by comparing consecutive fund balances.

        Deposit confirmation is derived ONLY from USVSST postings.
        """
        rows = conn.execute(
            "SELECT balance_amount, recorded_at FROM fund_balances ORDER BY id DESC LIMIT 2"
        ).fetchall()
        if len(rows) < 2:
            return
        current, previous = float(rows[0]["balance_amount"]), float(rows[1]["balance_amount"])
        diff = current - previous
        if diff > 0:
            conn.execute(
                "INSERT INTO deposits (job_run_id, amount, source_posting, deposit_date, confirmed, confirmed_at) "
                "VALUES (?, ?, ?, datetime('now'), 1, datetime('now'))",
                (run_id, diff, "USVSST fund_balance increase"),
            )
            logger.info("Confirmed deposit of $%.2f from USVSST posting", diff)
