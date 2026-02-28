"""
SQLite database models and schema management.

All authoritative facts (deposits, balances, cases, snapshots, alerts)
are stored here.  Only deterministic job logic may write to these tables.
LLM helpers may only READ from them and write to advisory-only columns
(e.g. memo_text, advisory_tags).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# ── Schema version (bump when migrations are needed) ──────────────────
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Job execution log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name        TEXT    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('pending','running','succeeded','failed')),
    started_at      TEXT,
    finished_at     TEXT,
    attempt         INTEGER NOT NULL DEFAULT 1,
    error_message   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_status ON job_runs(job_name, status);
CREATE INDEX IF NOT EXISTS idx_job_runs_created ON job_runs(created_at);

-- ── Source snapshots (raw HTML / text stored per fetch) ───────────────
CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT    NOT NULL,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    url             TEXT    NOT NULL,
    content_hash    TEXT    NOT NULL,
    raw_content     TEXT,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_snapshots_source ON snapshots(source_name);

-- ── Fund balance history (USVSST) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS fund_balances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    balance_amount  REAL    NOT NULL,
    raw_text        TEXT,
    recorded_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fund_balances_recorded ON fund_balances(recorded_at);

-- ── Qualifying cases (USVSST) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS qualifying_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    case_name       TEXT    NOT NULL,
    case_details    TEXT,
    first_seen_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(case_name)
);

-- ── Confirmed deposits (derived ONLY from USVSST postings) ──────────
CREATE TABLE IF NOT EXISTS deposits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    amount          REAL    NOT NULL,
    source_posting  TEXT    NOT NULL,
    deposit_date    TEXT    NOT NULL,
    confirmed       INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0, 1)),
    confirmed_at    TEXT,
    recorded_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Enforcement / legal signal articles ──────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    source          TEXT    NOT NULL,          -- 'doj' or 'ofac'
    title           TEXT    NOT NULL,
    url             TEXT    NOT NULL UNIQUE,
    published_date  TEXT,
    content_hash    TEXT    NOT NULL,
    keyword_hits    TEXT,                       -- JSON list of matched keywords
    -- Advisory-only column (may be written by LLM classification helper)
    advisory_tags   TEXT,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);

-- ── DPI scores ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dpi_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER NOT NULL REFERENCES job_runs(id),
    score           REAL    NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    regularity      REAL    NOT NULL,
    recency         REAL    NOT NULL,
    trend           REAL    NOT NULL,
    computed_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Alerts (deterministic, rule-based) ───────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name       TEXT    NOT NULL,
    severity        TEXT    NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    message         TEXT    NOT NULL,
    evidence        TEXT    NOT NULL,          -- JSON: deterministic evidence trail
    acknowledged    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

-- ── Advisory memos (LLM-generated, non-authoritative) ───────────────
CREATE TABLE IF NOT EXISTS memos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id      INTEGER REFERENCES job_runs(id),
    memo_text       TEXT    NOT NULL,
    generated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """Thin wrapper around SQLite for the Agent Manager."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            cur = conn.execute(
                "SELECT MAX(version) as v FROM schema_version"
            )
            row = cur.fetchone()
            if row["v"] is None or row["v"] < SCHEMA_VERSION:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )

    # ── Convenience query helpers ─────────────────────────────────────

    def insert_job_run(
        self, conn: sqlite3.Connection, job_name: str, status: str, attempt: int = 1
    ) -> int:
        cur = conn.execute(
            "INSERT INTO job_runs (job_name, status, attempt, started_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (job_name, status, attempt),
        )
        return cur.lastrowid  # type: ignore[return-value]

    def update_job_run(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE job_runs SET status = ?, finished_at = datetime('now'), "
            "error_message = ? WHERE id = ?",
            (status, error_message, run_id),
        )

    def latest_value(
        self, conn: sqlite3.Connection, table: str, column: str, order_col: str = "id"
    ) -> object | None:
        cur = conn.execute(
            f"SELECT {column} FROM {table} ORDER BY {order_col} DESC LIMIT 1"  # noqa: S608
        )
        row = cur.fetchone()
        return row[column] if row else None

    def latest_two_values(
        self, conn: sqlite3.Connection, table: str, column: str, order_col: str = "id"
    ) -> tuple[object | None, object | None]:
        cur = conn.execute(
            f"SELECT {column} FROM {table} ORDER BY {order_col} DESC LIMIT 2"  # noqa: S608
        )
        rows = cur.fetchall()
        if len(rows) == 0:
            return None, None
        if len(rows) == 1:
            return rows[0][column], None
        return rows[0][column], rows[1][column]
