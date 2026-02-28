"""
Deterministic alerting rules engine.

Alerts are triggered ONLY by deterministic comparisons of stored
numeric/text values against configured thresholds.  No LLM involvement.

Every alert carries an `evidence` JSON blob that makes it fully
explainable and reproducible.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from agent_manager.models import Database


@dataclass(frozen=True)
class AlertResult:
    """An alert produced by a deterministic rule evaluation."""
    rule_name: str
    severity: str
    message: str
    evidence: dict[str, Any]


class AlertRulesEngine:
    """Evaluate alert rules deterministically against stored data."""

    def __init__(self, rules: dict[str, dict], db: Database) -> None:
        self._rules = rules
        self._db = db

    def evaluate_all(self, conn: sqlite3.Connection) -> list[AlertResult]:
        """Evaluate every configured rule and return triggered alerts."""
        results: list[AlertResult] = []
        for rule_name, rule_cfg in self._rules.items():
            result = self._evaluate_rule(conn, rule_name, rule_cfg)
            if result is not None:
                results.append(result)
        return results

    def _evaluate_rule(
        self, conn: sqlite3.Connection, rule_name: str, cfg: dict
    ) -> AlertResult | None:
        field = cfg["field"]
        condition = cfg["condition"]
        threshold = cfg["threshold"]
        severity = cfg["severity"]

        if field == "fund_balance":
            return self._eval_fund_balance(conn, rule_name, condition, threshold, severity)
        if field == "qualifying_case_count":
            return self._eval_qualifying_cases(conn, rule_name, condition, threshold, severity)
        if field == "dpi_score":
            return self._eval_dpi(conn, rule_name, condition, threshold, severity)
        if field == "keyword_matches":
            return self._eval_keyword_matches(conn, rule_name, condition, threshold, severity)
        return None

    # ── Individual field evaluators ───────────────────────────────────

    def _eval_fund_balance(
        self,
        conn: sqlite3.Connection,
        rule_name: str,
        condition: str,
        threshold: float,
        severity: str,
    ) -> AlertResult | None:
        current, previous = self._db.latest_two_values(
            conn, "fund_balances", "balance_amount"
        )
        if current is None or previous is None:
            return None

        diff = abs(float(current) - float(previous))
        if condition == "abs_change_gte" and diff >= threshold:
            return AlertResult(
                rule_name=rule_name,
                severity=severity,
                message=(
                    f"Fund balance changed by ${diff:,.2f} "
                    f"(${float(previous):,.2f} → ${float(current):,.2f})"
                ),
                evidence={
                    "rule": rule_name,
                    "condition": condition,
                    "threshold": threshold,
                    "previous_balance": float(previous),
                    "current_balance": float(current),
                    "abs_change": diff,
                },
            )
        return None

    def _eval_qualifying_cases(
        self,
        conn: sqlite3.Connection,
        rule_name: str,
        condition: str,
        threshold: int,
        severity: str,
    ) -> AlertResult | None:
        cur = conn.execute("SELECT COUNT(*) as cnt FROM qualifying_cases")
        total = cur.fetchone()["cnt"]

        cur2 = conn.execute(
            "SELECT COUNT(*) as cnt FROM qualifying_cases "
            "WHERE first_seen_at >= datetime('now', '-1 hour')"
        )
        recent = cur2.fetchone()["cnt"]

        if condition == "increase" and recent >= threshold:
            return AlertResult(
                rule_name=rule_name,
                severity=severity,
                message=f"{recent} new qualifying case(s) detected (total: {total})",
                evidence={
                    "rule": rule_name,
                    "condition": condition,
                    "threshold": threshold,
                    "new_cases": recent,
                    "total_cases": total,
                },
            )
        return None

    def _eval_dpi(
        self,
        conn: sqlite3.Connection,
        rule_name: str,
        condition: str,
        threshold: float,
        severity: str,
    ) -> AlertResult | None:
        score = self._db.latest_value(conn, "dpi_scores", "score")
        if score is None:
            return None

        score_f = float(score)
        if condition == "lt" and score_f < threshold:
            return AlertResult(
                rule_name=rule_name,
                severity=severity,
                message=f"DPI score {score_f:.3f} is below threshold {threshold}",
                evidence={
                    "rule": rule_name,
                    "condition": condition,
                    "threshold": threshold,
                    "current_dpi": score_f,
                },
            )
        return None

    def _eval_keyword_matches(
        self,
        conn: sqlite3.Connection,
        rule_name: str,
        condition: str,
        threshold: int,
        severity: str,
    ) -> AlertResult | None:
        cur = conn.execute(
            "SELECT COUNT(*) as cnt FROM articles "
            "WHERE keyword_hits IS NOT NULL "
            "AND fetched_at >= datetime('now', '-1 hour')"
        )
        count = cur.fetchone()["cnt"]
        if condition == "new_matches" and count >= threshold:
            # Fetch the actual matches for evidence
            cur2 = conn.execute(
                "SELECT title, keyword_hits, source FROM articles "
                "WHERE keyword_hits IS NOT NULL "
                "AND fetched_at >= datetime('now', '-1 hour')"
            )
            matches = [
                {"title": r["title"], "source": r["source"], "keywords": r["keyword_hits"]}
                for r in cur2.fetchall()
            ]
            return AlertResult(
                rule_name=rule_name,
                severity=severity,
                message=f"{count} new article(s) with keyword matches",
                evidence={
                    "rule": rule_name,
                    "condition": condition,
                    "threshold": threshold,
                    "match_count": count,
                    "matches": matches,
                },
            )
        return None

    def persist_alert(self, conn: sqlite3.Connection, alert: AlertResult) -> int:
        """Write an alert to the database. Returns the alert row ID."""
        cur = conn.execute(
            "INSERT INTO alerts (rule_name, severity, message, evidence) "
            "VALUES (?, ?, ?, ?)",
            (alert.rule_name, alert.severity, alert.message, json.dumps(alert.evidence)),
        )
        return cur.lastrowid  # type: ignore[return-value]
