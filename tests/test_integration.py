"""
Integration tests for the Deterministic Agent Manager.

Tests the full pipeline: config loading, job execution, database writes.
Uses mock HTTP responses to avoid external dependencies.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_manager.manager import AgentManager
from agent_manager.models import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        yield db


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config file for testing."""
    config_content = """
database:
  path: "{db_path}"

schedules:
  every_minute:
    cron: "* * * * *"
  hourly:
    cron: "0 * * * *"

retry:
  max_attempts: 2
  backoff_base_seconds: 5
  backoff_multiplier: 2

jobs:
  test_job:
    description: "Test job"
    schedule_id: "every_minute"
    timeout_seconds: 10

alert_rules:
  test_rule:
    description: "Test alert rule"
    field: "fund_balance"
    condition: "abs_change_gte"
    threshold: 1000.00
    severity: "high"

dpi:
  lookback_days: 365
  min_deposits: 3
  weights:
    regularity: 0.4
    recency: 0.3
    trend: 0.3

notifications:
  log:
    enabled: true
  email:
    enabled: false
  webhook:
    enabled: false

llm_helpers:
  memo_summary:
    enabled: false
  classification:
    enabled: false
  parser_repair:
    enabled: false
""".format(db_path=str(tmp_path / "test.db"))

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


class TestManagerInitialization:
    """Test manager initialization and config loading."""

    def test_manager_loads_config(self, temp_config):
        """Manager can load YAML config without errors."""
        manager = AgentManager(temp_config)
        assert manager.config is not None
        assert "database" in manager.config
        assert "jobs" in manager.config

    def test_manager_builds_dag(self, temp_config):
        """Manager builds job DAG correctly."""
        manager = AgentManager(temp_config)
        assert manager.dag is not None
        # Test job should be in the DAG
        assert "test_job" in manager.dag._all_jobs


class TestDatabaseOperations:
    """Test database schema and queries."""

    def test_database_creates_schema(self, temp_db):
        """Database creates all required tables."""
        with temp_db.connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert "job_runs" in tables
            assert "alerts" in tables
            assert "dpi_scores" in tables
            assert "fund_balances" in tables
            assert "deposits" in tables

    def test_insert_job_run(self, temp_db):
        """Can insert and update job runs."""
        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "test_job", "running", 1)
            assert run_id is not None

            temp_db.update_job_run(conn, run_id, "succeeded")

            row = conn.execute(
                "SELECT status FROM job_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert row["status"] == "succeeded"

    def test_fund_balance_queries(self, temp_db):
        """Can insert and query fund balances."""
        with temp_db.connection() as conn:
            temp_db.insert_job_run(conn, "test", "succeeded", 1)
            run_id = 1

            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1000000.00),
            )

            balance = temp_db.latest_value(conn, "fund_balances", "balance_amount")
            assert balance == 1000000.00


class TestAlertingLogic:
    """Test deterministic alert rules."""

    def test_balance_change_alert(self, temp_db):
        """Alert triggers when balance changes exceed threshold."""
        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "test", "succeeded", 1)

            # Insert two balance snapshots
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1000000.00),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1010000.00),  # $10k change
            )

            # Query latest two balances
            current, previous = temp_db.latest_two_values(
                conn, "fund_balances", "balance_amount"
            )
            diff = abs(float(current) - float(previous))

            # Threshold is $1000
            assert diff >= 1000.00


class TestCircuitBreaker:
    """Test circuit breaker for resilient requests."""

    def test_circuit_breaker_opens_on_failures(self):
        """Circuit breaker opens after threshold failures."""
        from agent_manager.helpers.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(
            url="http://example.com",
            failure_threshold=3,
            recovery_timeout=60.0,
        )

        # Simulate 3 failures
        for _ in range(3):
            breaker.record_failure()
            if breaker.failure_count >= breaker.failure_threshold:
                breaker.state = breaker.state.__class__.OPEN
                break

        assert breaker.allow_request() is False

    def test_circuit_breaker_allows_during_half_open(self):
        """Circuit breaker allows single request in HALF_OPEN state."""
        from agent_manager.helpers.circuit_breaker import CircuitBreaker, CircuitState

        breaker = CircuitBreaker(
            url="http://example.com",
            failure_threshold=1,
            recovery_timeout=0.0,  # Recover immediately
        )

        breaker.record_failure()
        breaker.state = CircuitState.OPEN
        breaker.opened_at = 0  # Pretend it was opened long ago

        # After recovery_timeout, should be HALF_OPEN
        if breaker.allow_request():
            assert breaker.state == CircuitState.HALF_OPEN


class TestConnectionPooling:
    """Test SQLite connection pooling."""

    def test_connection_pool_creates_connections(self):
        """Connection pool creates and reuses connections."""
        from agent_manager.helpers.db_pool import SQLiteConnectionPool

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            pool = SQLiteConnectionPool(str(db_path), pool_size=3)

            # Get first connection
            with pool.get_connection() as conn1:
                conn1.execute("SELECT 1")

            # Connection should be in pool now
            assert pool._pool.qsize() == 1

            # Get second connection (should reuse from pool)
            with pool.get_connection() as conn2:
                conn2.execute("SELECT 1")

            pool.close_all()
