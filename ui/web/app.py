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
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, REGISTRY as prometheus_registry

import yaml

from agent_manager.helpers.metrics import REGISTRY, update_metrics_from_db

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


# ── Health check ────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Health check endpoint for monitoring and container orchestration."""
    checks: dict[str, Any] = {"status": "healthy"}

    # Verify database is accessible
    try:
        db = _db_path()
        if not db.exists():
            checks["status"] = "unhealthy"
            checks["database"] = "file not found"
        else:
            conn = sqlite3.connect(str(db))
            conn.execute("SELECT 1")
            conn.close()
            checks["database"] = "ok"
    except Exception as e:
        checks["status"] = "unhealthy"
        checks["database"] = str(e)

    # Verify config is loadable
    try:
        _get_config()
        checks["config"] = "ok"
    except Exception as e:
        checks["status"] = "unhealthy"
        checks["config"] = str(e)

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    update_metrics_from_db(_db_path())
    return Response(content=generate_latest(REGISTRY), media_type="text/plain; charset=utf-8")


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


@app.get("/api/alert-analytics")
def api_alert_analytics():
    """Alert history and analytics."""
    db = _db_path()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    try:
        # Alerts by severity (all time)
        severity_stats = _query(
            "SELECT severity, COUNT(*) as count FROM alerts GROUP BY severity ORDER BY severity"
        )

        # Alerts by rule (all time)
        rule_stats = _query(
            "SELECT rule_name, COUNT(*) as count, COUNT(CASE WHEN acknowledged=1 THEN 1 END) as acknowledged "
            "FROM alerts GROUP BY rule_name ORDER BY count DESC"
        )

        # Acknowledgement rate
        ack_stats = _query_one(
            "SELECT "
            "COUNT(*) as total, "
            "COUNT(CASE WHEN acknowledged=1 THEN 1 END) as acknowledged, "
            "CAST(COUNT(CASE WHEN acknowledged=1 THEN 1 END) AS FLOAT) / COUNT(*) as ack_rate "
            "FROM alerts"
        )

        # Recent alerts (last 24 hours)
        recent = _query(
            "SELECT severity, COUNT(*) as count FROM alerts "
            "WHERE created_at >= datetime('now', '-1 day') "
            "GROUP BY severity ORDER BY severity"
        )

        return {
            "severity_distribution": severity_stats,
            "rule_statistics": rule_stats,
            "acknowledgement": {
                "total": ack_stats["total"] if ack_stats else 0,
                "acknowledged": ack_stats["acknowledged"] if ack_stats else 0,
                "rate": float(ack_stats["ack_rate"]) if ack_stats and ack_stats["ack_rate"] else 0,
            },
            "recent_24h": recent,
        }
    finally:
        conn.close()


# ── HTML frontend ───────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the single-page dashboard."""
    html_path = _HERE / "templates" / "dashboard.html"
    return html_path.read_text()
