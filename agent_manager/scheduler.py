"""
Deterministic schedule evaluator.

Evaluates cron expressions from config.yaml to decide whether a job
is due to run at a given point in time.  Purely rule-based — no LLM.
"""

from __future__ import annotations

from datetime import datetime


class CronExpression:
    """Minimal cron parser supporting: minute, hour, day-of-month, month, day-of-week.

    Supports:
      - exact values: "5"
      - wildcards: "*"
      - step values: "*/15"
      - lists: "1,3,5"
      - ranges: "1-5"
    """

    def __init__(self, expr: str) -> None:
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron expression must have 5 fields, got {len(parts)}: {expr!r}")
        self.minute_expr = parts[0]
        self.hour_expr = parts[1]
        self.dom_expr = parts[2]
        self.month_expr = parts[3]
        self.dow_expr = parts[4]

    def matches(self, dt: datetime) -> bool:
        """Return True if the given datetime matches this cron expression."""
        return (
            self._field_matches(self.minute_expr, dt.minute, 0, 59)
            and self._field_matches(self.hour_expr, dt.hour, 0, 23)
            and self._field_matches(self.dom_expr, dt.day, 1, 31)
            and self._field_matches(self.month_expr, dt.month, 1, 12)
            and self._field_matches(self.dow_expr, dt.isoweekday() % 7, 0, 6)
        )

    @staticmethod
    def _field_matches(expr: str, value: int, min_val: int, max_val: int) -> bool:
        """Check if a single cron field matches the given value."""
        for part in expr.split(","):
            if CronExpression._part_matches(part.strip(), value, min_val, max_val):
                return True
        return False

    @staticmethod
    def _part_matches(part: str, value: int, min_val: int, max_val: int) -> bool:
        if part == "*":
            return True

        # Step: */N or M-N/S
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if base == "*":
                return (value - min_val) % step == 0
            if "-" in base:
                lo, hi = base.split("-", 1)
                return int(lo) <= value <= int(hi) and (value - int(lo)) % step == 0
            return value == int(base)

        # Range: M-N
        if "-" in part:
            lo, hi = part.split("-", 1)
            return int(lo) <= value <= int(hi)

        # Exact value
        return value == int(part)


class ScheduleEvaluator:
    """Evaluates whether jobs should run based on cron schedules from config."""

    def __init__(self, schedules: dict[str, dict]) -> None:
        self._crons: dict[str, CronExpression] = {}
        for schedule_id, schedule_cfg in schedules.items():
            self._crons[schedule_id] = CronExpression(schedule_cfg["cron"])

    def is_due(self, schedule_id: str, at: datetime) -> bool:
        """Return True if the schedule fires at the given time (minute-level)."""
        cron = self._crons.get(schedule_id)
        if cron is None:
            raise KeyError(f"Unknown schedule_id: {schedule_id!r}")
        return cron.matches(at)

    def due_schedules(self, at: datetime) -> list[str]:
        """Return all schedule IDs that match the given time."""
        return [sid for sid in self._crons if self.is_due(sid, at)]
