"""
Alert Dispatcher Job

Evaluates all configured alert rules deterministically and persists
any triggered alerts.  Optionally dispatches notifications via
configured channels (log, email, webhook).

No LLM involvement in alert triggering or dispatch decisions.
"""

from __future__ import annotations

import json
import logging
import smtplib
import sqlite3
from email.message import EmailMessage
from typing import Any
from urllib.request import Request, urlopen

from agent_manager.alerting import AlertResult, AlertRulesEngine
from agent_manager.jobs.base import BaseJob
from agent_manager.models import Database

logger = logging.getLogger(__name__)


class AlertDispatcherJob(BaseJob):
    name = "alert_dispatcher"

    def __init__(
        self,
        config: dict[str, Any],
        db: Database,
        alert_rules: dict[str, dict],
        notification_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config, db)
        self.engine = AlertRulesEngine(alert_rules, db)
        self.notification_config = notification_config or {}

    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        alerts = self.engine.evaluate_all(conn)
        logger.info("Evaluated alert rules: %d alert(s) triggered", len(alerts))

        for alert in alerts:
            alert_id = self.engine.persist_alert(conn, alert)
            logger.info(
                "Alert #%d [%s] %s: %s",
                alert_id, alert.severity, alert.rule_name, alert.message,
            )
            self._dispatch(alert)

    def _dispatch(self, alert: AlertResult) -> None:
        """Send alert through configured notification channels."""
        if self.notification_config.get("log", {}).get("enabled", True):
            self._dispatch_log(alert)
        if self.notification_config.get("email", {}).get("enabled", False):
            self._dispatch_email(alert)
        if self.notification_config.get("webhook", {}).get("enabled", False):
            self._dispatch_webhook(alert)

    def _dispatch_log(self, alert: AlertResult) -> None:
        level = logging.WARNING if alert.severity in ("high", "critical") else logging.INFO
        logger.log(
            level,
            "ALERT [%s] %s — %s | evidence: %s",
            alert.severity.upper(),
            alert.rule_name,
            alert.message,
            json.dumps(alert.evidence, default=str),
        )

    def _dispatch_email(self, alert: AlertResult) -> None:
        email_cfg = self.notification_config.get("email", {})
        smtp_host = email_cfg.get("smtp_host", "")
        smtp_port = email_cfg.get("smtp_port", 587)
        from_addr = email_cfg.get("from_address", "")
        to_addrs = email_cfg.get("to_addresses", [])

        if not smtp_host or not from_addr or not to_addrs:
            logger.warning("Email notification enabled but not fully configured")
            return

        severity_label = alert.severity.upper()
        msg = EmailMessage()
        msg["Subject"] = f"[{severity_label}] Agent Manager Alert: {alert.rule_name}"
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.set_content(
            f"Rule: {alert.rule_name}\n"
            f"Severity: {severity_label}\n"
            f"Message: {alert.message}\n\n"
            f"Evidence:\n{json.dumps(alert.evidence, indent=2, default=str)}\n"
        )

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                username = email_cfg.get("username")
                password = email_cfg.get("password")
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
            logger.info("Email alert dispatched to %s", to_addrs)
        except Exception as exc:
            logger.error("Email dispatch failed: %s", exc)

    def _dispatch_webhook(self, alert: AlertResult) -> None:
        url = self.notification_config.get("webhook", {}).get("url", "")
        if not url:
            return
        payload = json.dumps({
            "rule": alert.rule_name,
            "severity": alert.severity,
            "message": alert.message,
            "evidence": alert.evidence,
        }).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                logger.info("Webhook dispatched: %d", resp.status)
        except Exception as exc:
            logger.error("Webhook dispatch failed: %s", exc)
