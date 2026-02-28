"""Tests for the deterministic DPI calculator."""

from datetime import datetime, timedelta

import pytest

from agent_manager.jobs.dpi_calculator import DPICalculatorJob
from agent_manager.models import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def dpi_job(db):
    config = {"timeout_seconds": 60}
    dpi_config = {
        "lookback_days": 365,
        "min_deposits": 3,
        "weights": {"regularity": 0.4, "recency": 0.3, "trend": 0.3},
    }
    return DPICalculatorJob(config, db, dpi_config=dpi_config)


class TestRegularityScore:
    def test_perfect_regularity(self):
        # Equally spaced deposits
        now = datetime(2025, 6, 1)
        dates = [now - timedelta(days=i * 30) for i in range(5)]
        dates.reverse()
        score = DPICalculatorJob._regularity_score(dates)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_irregular_deposits(self):
        dates = [
            datetime(2025, 1, 1),
            datetime(2025, 1, 5),
            datetime(2025, 6, 1),
            datetime(2025, 6, 3),
        ]
        score = DPICalculatorJob._regularity_score(dates)
        assert score < 0.5

    def test_single_date(self):
        score = DPICalculatorJob._regularity_score([datetime(2025, 1, 1)])
        assert score == 0.0


class TestRecencyScore:
    def test_very_recent(self):
        dates = [datetime.utcnow()]
        score = DPICalculatorJob._recency_score(dates)
        assert score > 0.95

    def test_old_deposit(self):
        dates = [datetime.utcnow() - timedelta(days=365)]
        score = DPICalculatorJob._recency_score(dates)
        assert score == 0.0


class TestTrendScore:
    def test_increasing_amounts(self):
        amounts = [100, 200, 300, 400, 500]
        score = DPICalculatorJob._trend_score(amounts)
        assert score > 0.5

    def test_decreasing_amounts(self):
        amounts = [500, 400, 300, 200, 100]
        score = DPICalculatorJob._trend_score(amounts)
        assert score < 0.5

    def test_constant_amounts(self):
        amounts = [100, 100, 100, 100]
        score = DPICalculatorJob._trend_score(amounts)
        assert score == pytest.approx(0.5, abs=0.01)


class TestDPIExecution:
    def test_not_enough_deposits(self, dpi_job, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "dpi_calculator", "running")
            # Only 2 deposits (below min_deposits=3)
            now = datetime.utcnow()
            for i in range(2):
                conn.execute(
                    "INSERT INTO deposits (job_run_id, amount, source_posting, deposit_date, confirmed) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (run_id, 1000 + i * 100, "test", (now - timedelta(days=i * 30)).isoformat()),
                )
            dpi_job.execute(conn, run_id)
            # No DPI score should be written
            row = conn.execute("SELECT COUNT(*) as cnt FROM dpi_scores").fetchone()
            assert row["cnt"] == 0

    def test_enough_deposits(self, dpi_job, db):
        with db.connection() as conn:
            run_id = db.insert_job_run(conn, "dpi_calculator", "running")
            now = datetime.utcnow()
            for i in range(5):
                conn.execute(
                    "INSERT INTO deposits (job_run_id, amount, source_posting, deposit_date, confirmed) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (run_id, 1000 + i * 100, "test", (now - timedelta(days=i * 30)).isoformat()),
                )
            dpi_job.execute(conn, run_id)
            row = conn.execute("SELECT * FROM dpi_scores ORDER BY id DESC LIMIT 1").fetchone()
            assert row is not None
            assert 0.0 <= row["score"] <= 1.0
