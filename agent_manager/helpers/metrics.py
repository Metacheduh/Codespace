"""
Prometheus metrics for Agent Manager.

Tracks:
- Job execution counts and durations
- Alert counts by severity
- DPI score snapshots
- Fund balance trends
- Circuit breaker state
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

# Create a registry for metrics
REGISTRY = CollectorRegistry()

# ── Job metrics ────────────────────────────────────────────────
job_runs_total = Counter(
    "agent_manager_job_runs_total",
    "Total job runs by status",
    ["job_name", "status"],
    registry=REGISTRY,
)

job_run_duration_seconds = Histogram(
    "agent_manager_job_run_duration_seconds",
    "Job run duration in seconds",
    ["job_name"],
    registry=REGISTRY,
)

# ── Alert metrics ──────────────────────────────────────────────
alerts_total = Counter(
    "agent_manager_alerts_total",
    "Total alerts by severity and rule",
    ["rule_name", "severity"],
    registry=REGISTRY,
)

alerts_acknowledged = Counter(
    "agent_manager_alerts_acknowledged_total",
    "Acknowledged alerts by severity",
    ["severity"],
    registry=REGISTRY,
)

open_alerts = Gauge(
    "agent_manager_alerts_open",
    "Number of open (unacknowledged) alerts",
    registry=REGISTRY,
)

# ── DPI metrics ────────────────────────────────────────────────
dpi_score = Gauge(
    "agent_manager_dpi_score",
    "Latest Deposit Predictability Index score (0-1)",
    registry=REGISTRY,
)

dpi_regularity = Gauge(
    "agent_manager_dpi_regularity",
    "DPI regularity component",
    registry=REGISTRY,
)

dpi_recency = Gauge(
    "agent_manager_dpi_recency",
    "DPI recency component",
    registry=REGISTRY,
)

dpi_trend = Gauge(
    "agent_manager_dpi_trend",
    "DPI trend component",
    registry=REGISTRY,
)

# ── Fund balance metrics ───────────────────────────────────────
fund_balance_dollars = Gauge(
    "agent_manager_fund_balance_dollars",
    "Latest fund balance in dollars",
    registry=REGISTRY,
)

# ── Circuit breaker metrics ────────────────────────────────────
circuit_breaker_state = Gauge(
    "agent_manager_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
    ["url"],
    registry=REGISTRY,
)

circuit_breaker_failures = Gauge(
    "agent_manager_circuit_breaker_failures",
    "Failure count for circuit breaker",
    ["url"],
    registry=REGISTRY,
)


def update_metrics_from_db(db_path: str | Path) -> None:
    """Update all metrics from the database."""
    db_path = Path(db_path)
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        # DPI score
        dpi_row = conn.execute(
            "SELECT score, regularity, recency, trend FROM dpi_scores ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if dpi_row:
            dpi_score.set(float(dpi_row["score"]))
            dpi_regularity.set(float(dpi_row["regularity"]))
            dpi_recency.set(float(dpi_row["recency"]))
            dpi_trend.set(float(dpi_row["trend"]))

        # Fund balance
        balance_row = conn.execute(
            "SELECT balance_amount FROM fund_balances ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if balance_row:
            fund_balance_dollars.set(float(balance_row["balance_amount"]))

        # Open alerts
        alert_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM alerts WHERE acknowledged = 0"
        ).fetchone()
        if alert_count:
            open_alerts.set(alert_count["cnt"])

    finally:
        conn.close()
