"""
Deterministic Agent Manager  — the central orchestrator.

All decisions are driven by:
  - config.yaml rules (thresholds, keywords, retry/backoff)
  - cron schedules
  - DAG job dependencies
  - explicit state-machine transitions (pending → running → succeeded/failed)

NO LLM is used to decide what jobs to run, when to run them, whether a
deposit is confirmed, whether to trigger alerts, how to update job
status, or how to compute DPI.
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agent_manager.alerting import AlertRulesEngine
from agent_manager.dag import JobDAG
from agent_manager.jobs.alert_dispatcher import AlertDispatcherJob
from agent_manager.jobs.base import BaseJob
from agent_manager.jobs.doj_monitor import DOJMonitorJob
from agent_manager.jobs.dpi_calculator import DPICalculatorJob
from agent_manager.jobs.ofac_monitor import OFACMonitorJob
from agent_manager.jobs.usvsst_scraper import USVSSTScraperJob
from agent_manager.models import Database
from agent_manager.scheduler import ScheduleEvaluator
from agent_manager.state_machine import JobState, can_retry, transition

logger = logging.getLogger(__name__)

# ── Job registry (deterministic mapping from name → class) ────────────
JOB_REGISTRY: dict[str, type[BaseJob]] = {
    "usvsst_scraper": USVSSTScraperJob,
    "doj_monitor": DOJMonitorJob,
    "ofac_monitor": OFACMonitorJob,
    "dpi_calculator": DPICalculatorJob,
    "alert_dispatcher": AlertDispatcherJob,
}


class AgentManager:
    """Deterministic, rule-based orchestrator for monitoring jobs."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.db = Database(self.config["database"]["path"])
        self.scheduler = ScheduleEvaluator(self.config["schedules"])
        self.dag = self._build_dag()
        self._retry_cfg = self.config.get("retry", {})

    def _load_config(self) -> dict[str, Any]:
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _build_dag(self) -> JobDAG:
        dag = JobDAG()
        for job_name, job_cfg in self.config.get("jobs", {}).items():
            dag.add_job(job_name, job_cfg.get("depends_on"))
        dag.validate()
        return dag

    def _build_job(self, job_name: str) -> BaseJob:
        """Instantiate a job by name from the registry.  Deterministic lookup."""
        job_cls = JOB_REGISTRY.get(job_name)
        if job_cls is None:
            raise ValueError(f"Unknown job: {job_name!r}")

        job_cfg = self.config["jobs"][job_name]

        if job_name == "dpi_calculator":
            return job_cls(job_cfg, self.db, dpi_config=self.config.get("dpi"))
        if job_name == "alert_dispatcher":
            return job_cls(
                job_cfg,
                self.db,
                alert_rules=self.config.get("alert_rules", {}),
                notification_config=self.config.get("notifications"),
            )
        return job_cls(job_cfg, self.db)

    # ── Main tick (called once per minute by external scheduler) ──────

    def tick(self, now: datetime | None = None) -> list[str]:
        """Evaluate schedules, resolve dependencies, and run due jobs.

        Returns the list of job names that were executed in this tick.
        This method is fully deterministic given the same `now`, config,
        and database state.
        """
        now = now or datetime.utcnow().replace(second=0, microsecond=0)
        logger.info("Tick at %s", now.isoformat())

        # 1. Determine which schedules fire now
        due_schedule_ids = set(self.scheduler.due_schedules(now))

        # 2. Map schedules to jobs
        due_jobs: set[str] = set()
        for job_name, job_cfg in self.config.get("jobs", {}).items():
            if job_cfg.get("schedule_id") in due_schedule_ids:
                due_jobs.add(job_name)

        if not due_jobs:
            logger.info("No jobs due at %s", now.isoformat())
            return []

        # 3. Resolve execution order via DAG (topological sort)
        execution_order = self.dag.topological_order()

        # 4. Execute jobs in order, respecting dependencies
        succeeded: set[str] = set()
        executed: list[str] = []

        for job_name in execution_order:
            if job_name not in due_jobs:
                # Not due — but mark as "succeeded" for dependency purposes
                # if its last run succeeded
                if self._last_run_succeeded(job_name):
                    succeeded.add(job_name)
                continue

            # Check dependency readiness (deterministic DAG check)
            if not self.dag.is_ready(job_name, succeeded):
                logger.warning(
                    "Skipping %s: dependencies not met (%s)",
                    job_name,
                    self.dag.get_dependencies(job_name),
                )
                continue

            success = self._run_job_with_retry(job_name)
            if success:
                succeeded.add(job_name)
            executed.append(job_name)

        return executed

    def _run_job_with_retry(self, job_name: str) -> bool:
        """Run a job with deterministic retry/backoff from config."""
        max_attempts = self._retry_cfg.get("max_attempts", 3)
        backoff_base = self._retry_cfg.get("backoff_base_seconds", 60)
        backoff_mult = self._retry_cfg.get("backoff_multiplier", 2)

        for attempt in range(1, max_attempts + 1):
            success = self._run_job(job_name, attempt)
            if success:
                return True
            if attempt < max_attempts:
                wait = backoff_base * (backoff_mult ** (attempt - 1))
                logger.info("Retrying %s in %ds (attempt %d/%d)", job_name, wait, attempt + 1, max_attempts)
                time.sleep(wait)
        return False

    def _run_job(self, job_name: str, attempt: int) -> bool:
        """Execute a single job run with state-machine transitions."""
        job = self._build_job(job_name)

        with self.db.connection() as conn:
            # State: pending → running
            run_id = self.db.insert_job_run(conn, job_name, JobState.RUNNING.value, attempt)
            transition(JobState.PENDING, JobState.RUNNING, reason=f"Starting {job_name}")

            try:
                job.execute(conn, run_id)
                # State: running → succeeded
                self.db.update_job_run(conn, run_id, JobState.SUCCEEDED.value)
                transition(JobState.RUNNING, JobState.SUCCEEDED, reason=f"{job_name} completed")
                logger.info("Job %s succeeded (run #%d, attempt %d)", job_name, run_id, attempt)
                return True
            except Exception as exc:
                # State: running → failed
                error_msg = f"{type(exc).__name__}: {exc}"
                self.db.update_job_run(conn, run_id, JobState.FAILED.value, error_msg)
                transition(JobState.RUNNING, JobState.FAILED, reason=error_msg)
                logger.error("Job %s failed (attempt %d): %s", job_name, attempt, error_msg)
                logger.debug(traceback.format_exc())
                return False

    def _last_run_succeeded(self, job_name: str) -> bool:
        """Check if the most recent run of a job succeeded."""
        with self.db.connection() as conn:
            cur = conn.execute(
                "SELECT status FROM job_runs WHERE job_name = ? "
                "ORDER BY id DESC LIMIT 1",
                (job_name,),
            )
            row = cur.fetchone()
            return row is not None and row["status"] == JobState.SUCCEEDED.value

    # ── Manual / one-shot execution ──────────────────────────────────

    def run_job(self, job_name: str) -> bool:
        """Run a single job immediately (for manual/testing use)."""
        return self._run_job_with_retry(job_name)

    def run_all(self) -> list[str]:
        """Run all jobs in DAG order (for manual/testing use)."""
        order = self.dag.topological_order()
        executed: list[str] = []
        succeeded: set[str] = set()
        for job_name in order:
            if not self.dag.is_ready(job_name, succeeded):
                logger.warning("Skipping %s: dependencies not met", job_name)
                continue
            success = self._run_job_with_retry(job_name)
            if success:
                succeeded.add(job_name)
            executed.append(job_name)
        return executed
