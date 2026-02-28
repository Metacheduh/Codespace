"""
Memo / Summary Helper  (optional, advisory only).

Generates narrative summaries from ALREADY-CONFIRMED facts in SQLite.
Output goes to the `memos` table only — never modifies authoritative
facts, confirms deposits, or triggers alerts.

This module is entirely optional and can be disabled in config.yaml.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from agent_manager.models import Database

logger = logging.getLogger(__name__)


class MemoHelper:
    """Generate advisory narrative memos from confirmed database facts.

    CONSTRAINTS:
      - Reads ONLY from SQLite (confirmed facts).
      - Writes ONLY to the `memos` table (advisory text).
      - NEVER modifies fund_balances, deposits, alerts, dpi_scores,
        qualifying_cases, or any other authoritative table.
      - NEVER triggers alerts or changes confirmed status.
    """

    def __init__(self, config: dict[str, Any], db: Database) -> None:
        self.enabled = config.get("enabled", False)
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 1024)
        self.db = db

    def generate_memo(
        self,
        conn: sqlite3.Connection,
        run_id: int | None = None,
        llm_callable: Any | None = None,
    ) -> str | None:
        """Generate an advisory memo from confirmed facts.

        Args:
            conn: Database connection (read-only usage for facts).
            run_id: Optional job_run_id to associate with the memo.
            llm_callable: Optional callable(prompt: str) -> str.
                          If None or disabled, returns a deterministic summary.

        Returns:
            The memo text, or None if disabled.
        """
        if not self.enabled:
            logger.debug("Memo helper is disabled")
            return None

        facts = self._gather_facts(conn)

        if llm_callable is not None:
            prompt = self._build_prompt(facts)
            try:
                memo_text = llm_callable(prompt)
            except Exception as exc:
                logger.warning("LLM memo generation failed, falling back to deterministic: %s", exc)
                memo_text = self._deterministic_summary(facts)
        else:
            memo_text = self._deterministic_summary(facts)

        # Write ONLY to advisory memos table
        conn.execute(
            "INSERT INTO memos (job_run_id, memo_text) VALUES (?, ?)",
            (run_id, memo_text),
        )
        return memo_text

    def _gather_facts(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """Read confirmed facts from the database (read-only)."""
        facts: dict[str, Any] = {}

        # Latest fund balance
        row = conn.execute(
            "SELECT balance_amount, recorded_at FROM fund_balances ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            facts["latest_balance"] = {"amount": row["balance_amount"], "as_of": row["recorded_at"]}

        # Recent deposits
        rows = conn.execute(
            "SELECT amount, deposit_date FROM deposits WHERE confirmed = 1 "
            "ORDER BY deposit_date DESC LIMIT 5"
        ).fetchall()
        facts["recent_deposits"] = [{"amount": r["amount"], "date": r["deposit_date"]} for r in rows]

        # Latest DPI
        row = conn.execute("SELECT score, computed_at FROM dpi_scores ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            facts["latest_dpi"] = {"score": row["score"], "as_of": row["computed_at"]}

        # Recent alerts
        rows = conn.execute(
            "SELECT rule_name, severity, message, created_at FROM alerts "
            "ORDER BY id DESC LIMIT 5"
        ).fetchall()
        facts["recent_alerts"] = [
            {"rule": r["rule_name"], "severity": r["severity"], "message": r["message"], "at": r["created_at"]}
            for r in rows
        ]

        # Qualifying case count
        row = conn.execute("SELECT COUNT(*) as cnt FROM qualifying_cases").fetchone()
        facts["qualifying_case_count"] = row["cnt"]

        return facts

    def _build_prompt(self, facts: dict[str, Any]) -> str:
        """Build an LLM prompt from gathered facts."""
        lines = ["Summarize the following victim-compensation monitoring facts into a brief memo:"]
        if "latest_balance" in facts:
            b = facts["latest_balance"]
            lines.append(f"- Current fund balance: ${b['amount']:,.2f} (as of {b['as_of']})")
        if facts.get("recent_deposits"):
            lines.append("- Recent confirmed deposits:")
            for d in facts["recent_deposits"]:
                lines.append(f"  - ${d['amount']:,.2f} on {d['date']}")
        if "latest_dpi" in facts:
            d = facts["latest_dpi"]
            lines.append(f"- DPI score: {d['score']:.3f} (as of {d['as_of']})")
        lines.append(f"- Total qualifying cases: {facts.get('qualifying_case_count', 0)}")
        if facts.get("recent_alerts"):
            lines.append("- Recent alerts:")
            for a in facts["recent_alerts"]:
                lines.append(f"  - [{a['severity']}] {a['rule']}: {a['message']}")
        return "\n".join(lines)

    @staticmethod
    def _deterministic_summary(facts: dict[str, Any]) -> str:
        """Fallback deterministic summary (no LLM needed)."""
        parts: list[str] = []
        if "latest_balance" in facts:
            b = facts["latest_balance"]
            parts.append(f"Fund balance: ${b['amount']:,.2f} (as of {b['as_of']}).")
        if facts.get("recent_deposits"):
            count = len(facts["recent_deposits"])
            total = sum(d["amount"] for d in facts["recent_deposits"])
            parts.append(f"{count} recent deposit(s) totalling ${total:,.2f}.")
        if "latest_dpi" in facts:
            parts.append(f"DPI: {facts['latest_dpi']['score']:.3f}.")
        parts.append(f"Qualifying cases: {facts.get('qualifying_case_count', 0)}.")
        alert_count = len(facts.get("recent_alerts", []))
        if alert_count:
            parts.append(f"{alert_count} recent alert(s).")
        return " ".join(parts) if parts else "No data available."
