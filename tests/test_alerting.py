"""Tests for the deterministic alerting rules engine."""

import json

import pytest

from agent_manager.alerting import AlertRulesEngine
from agent_manager.models import Database

TEST_RULES = {
    "balance_change": {
        "field": "fund_balance",
        "condition": "abs_change_gte",
        "threshold": 1000.0,
        "severity": "high",
    },
    "dpi_drop": {
        "field": "dpi_score",
        "condition": "lt",
        "threshold": 0.4,
        "severity": "high",
    },
}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def engine(db):
    return AlertRulesEngine(TEST_RULES, db)


class TestFundBalanceAlert:
    def test_no_alert_when_no_data(self, engine, db):
        with db.connection() as conn:
            alerts = engine.evaluate_all(conn)
        assert len(alerts) == 0

    def test_no_alert_below_threshold(self, engine, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100000.0),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100500.0),
            )
            alerts = engine.evaluate_all(conn)
        balance_alerts = [a for a in alerts if a.rule_name == "balance_change"]
        assert len(balance_alerts) == 0

    def test_alert_above_threshold(self, engine, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100000.0),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 105000.0),
            )
            alerts = engine.evaluate_all(conn)
        balance_alerts = [a for a in alerts if a.rule_name == "balance_change"]
        assert len(balance_alerts) == 1
        assert balance_alerts[0].severity == "high"
        assert balance_alerts[0].evidence["abs_change"] == 5000.0


class TestDPIAlert:
    def test_no_alert_when_no_data(self, engine, db):
        with db.connection() as conn:
            alerts = engine.evaluate_all(conn)
        dpi_alerts = [a for a in alerts if a.rule_name == "dpi_drop"]
        assert len(dpi_alerts) == 0

    def test_alert_when_dpi_low(self, engine, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO dpi_scores (job_run_id, score, regularity, recency, trend) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, 0.25, 0.3, 0.2, 0.1),
            )
            alerts = engine.evaluate_all(conn)
        dpi_alerts = [a for a in alerts if a.rule_name == "dpi_drop"]
        assert len(dpi_alerts) == 1
        assert dpi_alerts[0].evidence["current_dpi"] == 0.25

    def test_no_alert_when_dpi_ok(self, engine, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO dpi_scores (job_run_id, score, regularity, recency, trend) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, 0.75, 0.8, 0.7, 0.6),
            )
            alerts = engine.evaluate_all(conn)
        dpi_alerts = [a for a in alerts if a.rule_name == "dpi_drop"]
        assert len(dpi_alerts) == 0


class TestAlertPersistence:
    def test_persist_alert(self, engine, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "test", "succeeded")
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 100000.0),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 110000.0),
            )
            alerts = engine.evaluate_all(conn)
            for alert in alerts:
                alert_id = engine.persist_alert(conn, alert)
                assert alert_id > 0

            # Verify alert was written
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            assert row["rule_name"] == "balance_change"
            assert row["severity"] == "high"
            evidence = json.loads(row["evidence"])
            assert evidence["abs_change"] == 10000.0
