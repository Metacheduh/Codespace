"""
FastAPI backend for the Deterministic Agent Manager dashboard.

Serves both the REST API and the single-page web frontend.
All data comes directly from the SQLite database (read-only).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import yaml

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"

app = FastAPI(title="Agent Manager Dashboard", version="0.1.0")

# Serve static assets (CSS/JS)
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


def _get_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _db_path() -> Path:
    cfg = _get_config()
    p = Path(cfg["database"]["path"])
    if not p.is_absolute():
        p = _ROOT / p
    return p


def _query(sql: str, params: tuple = (), limit: int = 100) -> list[dict]:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()[:limit]
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = _query(sql, params, limit=1)
    return rows[0] if rows else None


# ── API Routes ──────────────────────────────────────────────────────────


@app.get("/api/status")
def api_status():
    """Overall system status summary."""
    latest_run = _query_one(
        "SELECT job_name, status, finished_at FROM job_runs ORDER BY id DESC LIMIT 1"
    )
    total_runs = _query_one("SELECT COUNT(*) as count FROM job_runs")
    open_alerts = _query_one(
        "SELECT COUNT(*) as count FROM alerts WHERE acknowledged = 0"
    )
    latest_dpi = _query_one(
        "SELECT score, computed_at FROM dpi_scores ORDER BY id DESC LIMIT 1"
    )
    latest_balance = _query_one(
        "SELECT balance_amount, recorded_at FROM fund_balances ORDER BY id DESC LIMIT 1"
    )
    return {
        "latest_run": latest_run,
        "total_runs": total_runs["count"] if total_runs else 0,
        "open_alerts": open_alerts["count"] if open_alerts else 0,
        "latest_dpi": latest_dpi,
        "latest_balance": latest_balance,
    }


@app.get("/api/jobs")
def api_jobs(limit: int = Query(50, ge=1, le=500)):
    """Recent job runs."""
    return _query(
        "SELECT id, job_name, status, attempt, started_at, finished_at, "
        "error_message, created_at FROM job_runs ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/jobs/{job_name}")
def api_job_detail(job_name: str, limit: int = Query(20, ge=1, le=100)):
    """Run history for a specific job."""
    return _query(
        "SELECT id, status, attempt, started_at, finished_at, error_message "
        "FROM job_runs WHERE job_name = ? ORDER BY id DESC",
        (job_name,),
        limit=limit,
    )


@app.get("/api/alerts")
def api_alerts(
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Recent alerts, optionally filtered by severity."""
    if severity:
        return _query(
            "SELECT id, rule_name, severity, message, evidence, acknowledged, created_at "
            "FROM alerts WHERE severity = ? ORDER BY id DESC",
            (severity,),
            limit=limit,
        )
    return _query(
        "SELECT id, rule_name, severity, message, evidence, acknowledged, created_at "
        "FROM alerts ORDER BY id DESC",
        limit=limit,
    )


@app.post("/api/alerts/{alert_id}/acknowledge")
def api_acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged."""
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/dpi")
def api_dpi(limit: int = Query(30, ge=1, le=365)):
    """DPI score history."""
    return _query(
        "SELECT id, score, regularity, recency, trend, computed_at "
        "FROM dpi_scores ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/balances")
def api_balances(limit: int = Query(30, ge=1, le=365)):
    """Fund balance history."""
    return _query(
        "SELECT id, balance_amount, recorded_at FROM fund_balances ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/deposits")
def api_deposits(limit: int = Query(50, ge=1, le=500)):
    """Confirmed deposit records."""
    return _query(
        "SELECT id, amount, source_posting, deposit_date, confirmed, confirmed_at, recorded_at "
        "FROM deposits ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/articles")
def api_articles(
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Scraped articles from DOJ/OFAC."""
    if source:
        return _query(
            "SELECT id, source, title, url, published_date, keyword_hits, advisory_tags, fetched_at "
            "FROM articles WHERE source = ? ORDER BY id DESC",
            (source,),
            limit=limit,
        )
    return _query(
        "SELECT id, source, title, url, published_date, keyword_hits, advisory_tags, fetched_at "
        "FROM articles ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/cases")
def api_cases(limit: int = Query(50, ge=1, le=500)):
    """Qualifying cases."""
    return _query(
        "SELECT id, case_name, case_details, first_seen_at FROM qualifying_cases ORDER BY id DESC",
        limit=limit,
    )


@app.get("/api/config")
def api_config():
    """Current configuration (sanitized)."""
    cfg = _get_config()
    # Redact notification secrets
    notif = cfg.get("notifications", {})
    for channel in notif.values():
        if isinstance(channel, dict):
            for key in ("smtp_host", "from_address", "to_addresses", "url"):
                if key in channel:
                    channel[key] = "***"
    return cfg


# ── HTML frontend ───────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the single-page dashboard."""
    html_path = _HERE / "templates" / "dashboard.html"
    return html_path.read_text()
