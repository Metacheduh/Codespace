"""Tests for database models and schema."""

import pytest

from agent_manager.models import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


class TestDatabaseInit:
    def test_creates_tables(self, db):
        with db.connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            assert "job_runs" in table_names
            assert "snapshots" in table_names
            assert "fund_balances" in table_names
            assert "qualifying_cases" in table_names
            assert "deposits" in table_names
            assert "articles" in table_names
            assert "dpi_scores" in table_names
            assert "alerts" in table_names
            assert "memos" in table_names
            assert "schema_version" in table_names

    def test_schema_version(self, db):
        with db.connection() as conn:
            row = conn.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
            assert row["v"] == 1


class TestJobRuns:
    def test_insert_and_update(self, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test_job", "running")
            assert run_id > 0

            db.update_job_run(conn, run_id, "succeeded")

            row = conn.execute("SELECT * FROM job_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "succeeded"
            assert row["finished_at"] is not None

    def test_insert_failed_with_error(self, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test_job", "running")
            db.update_job_run(conn, run_id, "failed", "Connection timeout")

            row = conn.execute("SELECT * FROM job_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "failed"
            assert row["error_message"] == "Connection timeout"


class TestLatestValue:
    def test_latest_value_empty_table(self, db):
        with db.connection() as conn:
            val = db.latest_value(conn, "fund_balances", "balance_amount")
            assert val is None

    def test_latest_value(self, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100.0),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 200.0),
            )
            val = db.latest_value(conn, "fund_balances", "balance_amount")
            assert val == 200.0

    def test_latest_two_values(self, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100.0),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 200.0),
            )
            current, previous = db.latest_two_values(conn, "fund_balances", "balance_amount")
            assert current == 200.0
            assert previous == 100.0
