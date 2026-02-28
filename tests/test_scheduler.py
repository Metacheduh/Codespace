"""Tests for the deterministic schedule evaluator."""

from datetime import datetime

import pytest

from agent_manager.scheduler import CronExpression, ScheduleEvaluator


class TestCronExpression:
    def test_every_minute(self):
        cron = CronExpression("* * * * *")
        assert cron.matches(datetime(2025, 1, 1, 0, 0)) is True
        assert cron.matches(datetime(2025, 6, 15, 12, 30)) is True

    def test_exact_minute(self):
        cron = CronExpression("30 * * * *")
        assert cron.matches(datetime(2025, 1, 1, 0, 30)) is True
        assert cron.matches(datetime(2025, 1, 1, 0, 0)) is False

    def test_step_minutes(self):
        cron = CronExpression("*/15 * * * *")
        assert cron.matches(datetime(2025, 1, 1, 0, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 0, 15)) is True
        assert cron.matches(datetime(2025, 1, 1, 0, 30)) is True
        assert cron.matches(datetime(2025, 1, 1, 0, 45)) is True
        assert cron.matches(datetime(2025, 1, 1, 0, 10)) is False

    def test_hourly_at_zero(self):
        cron = CronExpression("0 * * * *")
        assert cron.matches(datetime(2025, 1, 1, 8, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 8, 1)) is False

    def test_specific_hour(self):
        cron = CronExpression("0 8 * * *")
        assert cron.matches(datetime(2025, 1, 1, 8, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 9, 0)) is False

    def test_step_hours(self):
        cron = CronExpression("0 */6 * * *")
        assert cron.matches(datetime(2025, 1, 1, 0, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 6, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 12, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 3, 0)) is False

    def test_day_of_week_monday(self):
        # Monday 2025-01-06
        cron = CronExpression("0 9 * * 1")
        assert cron.matches(datetime(2025, 1, 6, 9, 0)) is True
        # Tuesday 2025-01-07
        assert cron.matches(datetime(2025, 1, 7, 9, 0)) is False

    def test_range(self):
        cron = CronExpression("0 9-17 * * *")
        assert cron.matches(datetime(2025, 1, 1, 9, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 17, 0)) is True
        assert cron.matches(datetime(2025, 1, 1, 8, 0)) is False

    def test_invalid_expression(self):
        with pytest.raises(ValueError):
            CronExpression("* * *")


class TestScheduleEvaluator:
    def test_due_schedules(self):
        schedules = {
            "every_15_min": {"cron": "*/15 * * * *"},
            "hourly": {"cron": "0 * * * *"},
        }
        evaluator = ScheduleEvaluator(schedules)
        # At minute 0: both fire
        due = evaluator.due_schedules(datetime(2025, 1, 1, 0, 0))
        assert "every_15_min" in due
        assert "hourly" in due
        # At minute 15: only every_15_min fires
        due = evaluator.due_schedules(datetime(2025, 1, 1, 0, 15))
        assert "every_15_min" in due
        assert "hourly" not in due

    def test_unknown_schedule(self):
        evaluator = ScheduleEvaluator({"x": {"cron": "* * * * *"}})
        with pytest.raises(KeyError):
            evaluator.is_due("nonexistent", datetime(2025, 1, 1))
