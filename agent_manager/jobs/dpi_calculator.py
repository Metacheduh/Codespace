"""
Deposit Predictability Index (DPI) Calculator

Computes a 0–1 score from confirmed deposit history.  The calculation
is fully deterministic and parameterised by config.yaml weights.

Components:
  - Regularity: stddev of inter-deposit intervals (normalised)
  - Recency: days since last deposit (normalised)
  - Trend: slope of deposit amounts (normalised)
"""

from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from agent_manager.jobs.base import BaseJob
from agent_manager.models import Database

logger = logging.getLogger(__name__)


class DPICalculatorJob(BaseJob):
    name = "dpi_calculator"

    def __init__(self, config: dict[str, Any], db: Database, dpi_config: dict[str, Any] | None = None) -> None:
        super().__init__(config, db)
        dpi = dpi_config or {}
        self.lookback_days: int = dpi.get("lookback_days", 365)
        self.min_deposits: int = dpi.get("min_deposits", 3)
        weights = dpi.get("weights", {})
        self.w_regularity: float = weights.get("regularity", 0.4)
        self.w_recency: float = weights.get("recency", 0.3)
        self.w_trend: float = weights.get("trend", 0.3)

    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        cutoff = (datetime.utcnow() - timedelta(days=self.lookback_days)).isoformat()
        rows = conn.execute(
            "SELECT amount, deposit_date FROM deposits "
            "WHERE confirmed = 1 AND deposit_date >= ? "
            "ORDER BY deposit_date ASC",
            (cutoff,),
        ).fetchall()

        if len(rows) < self.min_deposits:
            logger.info(
                "Not enough confirmed deposits (%d < %d) to compute DPI",
                len(rows), self.min_deposits,
            )
            return

        amounts = [float(r["amount"]) for r in rows]
        dates = [datetime.fromisoformat(r["deposit_date"]) for r in rows]

        regularity = self._regularity_score(dates)
        recency = self._recency_score(dates)
        trend = self._trend_score(amounts)

        score = (
            self.w_regularity * regularity
            + self.w_recency * recency
            + self.w_trend * trend
        )
        score = max(0.0, min(1.0, score))

        conn.execute(
            "INSERT INTO dpi_scores (job_run_id, score, regularity, recency, trend) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, score, regularity, recency, trend),
        )
        logger.info(
            "DPI score: %.3f  (regularity=%.3f, recency=%.3f, trend=%.3f)",
            score, regularity, recency, trend,
        )

    # ── Component calculations (all deterministic) ───────────────────

    @staticmethod
    def _regularity_score(dates: list[datetime]) -> float:
        """Score 0–1 based on how regular the deposit intervals are.

        Perfect regularity → 1.0, high variance → 0.0.
        """
        if len(dates) < 2:
            return 0.0
        intervals = [
            (dates[i + 1] - dates[i]).total_seconds() / 86400
            for i in range(len(dates) - 1)
        ]
        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            return 0.0
        variance = sum((iv - mean_interval) ** 2 for iv in intervals) / len(intervals)
        cv = math.sqrt(variance) / mean_interval  # coefficient of variation
        return max(0.0, 1.0 - cv)

    @staticmethod
    def _recency_score(dates: list[datetime]) -> float:
        """Score 0–1 based on how recent the last deposit was.

        Last deposit today → 1.0, >180 days ago → 0.0.
        """
        if not dates:
            return 0.0
        days_since = (datetime.utcnow() - dates[-1]).total_seconds() / 86400
        return max(0.0, 1.0 - (days_since / 180.0))

    @staticmethod
    def _trend_score(amounts: list[float]) -> float:
        """Score 0–1 based on whether deposit amounts are increasing.

        Uses simple linear regression slope (normalised).
        Increasing → closer to 1.0, decreasing → closer to 0.0.
        """
        n = len(amounts)
        if n < 2:
            return 0.5
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(amounts) / n
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, amounts))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        if denominator == 0:
            return 0.5
        slope = numerator / denominator
        # Normalise: map slope to 0–1 range using sigmoid-like transform
        normalised = 1.0 / (1.0 + math.exp(-slope / max(y_mean, 1.0)))
        return normalised
