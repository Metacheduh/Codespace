"""Tests for the deterministic Agent Manager orchestrator."""

from datetime import datetime
from unittest.mock import patch

import pytest

from agent_manager.manager import AgentManager


@pytest.fixture
def config_path(tmp_path):
    config_content = """
database:
  path: "{db_path}"

schedules:
  every_min:
    cron: "* * * * *"
  hourly:
    cron: "0 * * * *"

retry:
  max_attempts: 1
  backoff_base_seconds: 0
  backoff_multiplier: 1

jobs:
  usvsst_scraper:
    description: "Test scraper"
    schedule_id: "hourly"
    timeout_seconds: 5
    sources: []

  dpi_calculator:
    description: "Test DPI"
    schedule_id: "hourly"
    timeout_seconds: 5
    depends_on:
      - "usvsst_scraper"

  alert_dispatcher:
    description: "Test alerts"
    schedule_id: "every_min"
    timeout_seconds: 5
    depends_on:
      - "usvsst_scraper"
      - "dpi_calculator"

alert_rules:
  balance_change:
    field: "fund_balance"
    condition: "abs_change_gte"
    threshold: 1000.0
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
""".format(db_path=str(tmp_path / "test.db"))

    cfg = tmp_path / "config.yaml"
    cfg.write_text(config_content)
    return cfg


class TestAgentManagerInit:
    def test_loads_config(self, config_path):
        mgr = AgentManager(config_path)
        assert "jobs" in mgr.config
        assert "schedules" in mgr.config

    def test_builds_dag(self, config_path):
        mgr = AgentManager(config_path)
        order = mgr.dag.topological_order()
        assert order.index("usvsst_scraper") < order.index("dpi_calculator")
        assert order.index("dpi_calculator") < order.index("alert_dispatcher")


class TestTickScheduling:
    def test_no_jobs_due(self, config_path):
        mgr = AgentManager(config_path)
        # Minute 30, hour 3: hourly jobs don't fire (they need minute 0)
        # every_min fires but depends on usvsst_scraper which isn't due
        executed = mgr.tick(datetime(2025, 1, 1, 3, 30))
        # alert_dispatcher is due (every_min), but usvsst_scraper is not
        # alert_dispatcher deps not met if usvsst hasn't run
        # Only alert_dispatcher is scheduled, but its deps aren't met
        assert "usvsst_scraper" not in executed

    def test_hourly_jobs_due(self, config_path):
        mgr = AgentManager(config_path)
        # At minute 0: hourly + every_min fire
        # usvsst_scraper will fail (no real URLs) but should be attempted
        with patch.object(mgr, "_run_job", return_value=True) as mock_run:
            executed = mgr.tick(datetime(2025, 1, 1, 0, 0))
            # All three should be attempted since mock returns True
            assert "usvsst_scraper" in executed
            assert "dpi_calculator" in executed
            assert "alert_dispatcher" in executed


class TestDependencyRespected:
    def test_downstream_skipped_on_upstream_failure(self, config_path):
        mgr = AgentManager(config_path)

        call_count = {"usvsst_scraper": 0, "dpi_calculator": 0, "alert_dispatcher": 0}

        def mock_run(job_name, attempt=1):
            call_count[job_name] = call_count.get(job_name, 0) + 1
            return job_name == "usvsst_scraper"  # Only scraper succeeds

        with patch.object(mgr, "_run_job", side_effect=mock_run):
            executed = mgr.tick(datetime(2025, 1, 1, 0, 0))

        assert "usvsst_scraper" in executed
        assert "dpi_calculator" in executed  # attempted (dep met)
        # alert_dispatcher depends on both usvsst + dpi; dpi failed
        assert "alert_dispatcher" not in executed
