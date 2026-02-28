"""
Terminal UI dashboard for the Deterministic Agent Manager.

Uses the `textual` library for a rich, interactive TUI.
Run: python -m ui.cli
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Rule,
    Static,
    TabbedContent,
    TabPane,
)

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"


def _get_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _db_path() -> Path:
    cfg = _get_config()
    p = Path(cfg["database"]["path"])
    if not p.is_absolute():
        p = _ROOT / p
    return p


def _query(sql: str, params: tuple = ()) -> list[dict]:
    db = _db_path()
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "---"
    return f"${v:,.2f}"


def _severity_markup(sev: str) -> str:
    colors = {"low": "green", "medium": "yellow", "high": "#fb923c", "critical": "red"}
    return f"[bold {colors.get(sev, 'white')}]{sev.upper()}[/]"


def _status_markup(status: str) -> str:
    colors = {"succeeded": "green", "failed": "red", "running": "yellow", "pending": "#fb923c"}
    return f"[bold {colors.get(status, 'white')}]{status}[/]"


# ── Status Bar Widget ──────────────────────────────────────────────────


class StatusBar(Static):
    """Top summary bar showing key metrics."""

    def compose(self) -> ComposeResult:
        yield Label("Loading...", id="status-text")

    def refresh_data(self) -> None:
        total = _query_one("SELECT COUNT(*) as c FROM job_runs")
        alerts = _query_one("SELECT COUNT(*) as c FROM alerts WHERE acknowledged = 0")
        dpi = _query_one("SELECT score FROM dpi_scores ORDER BY id DESC LIMIT 1")
        bal = _query_one("SELECT balance_amount FROM fund_balances ORDER BY id DESC LIMIT 1")

        total_c = total["c"] if total else 0
        alert_c = alerts["c"] if alerts else 0
        dpi_s = f"{dpi['score']:.3f}" if dpi else "---"
        bal_s = _fmt_money(bal["balance_amount"] if bal else None)

        alert_color = "red" if alert_c > 0 else "green"
        dpi_color = "green" if dpi and dpi["score"] >= 0.7 else "yellow" if dpi and dpi["score"] >= 0.4 else "red"
        if not dpi:
            dpi_color = "white"

        text = (
            f"  Runs: [bold]{total_c}[/]"
            f"   |   Alerts: [bold {alert_color}]{alert_c}[/]"
            f"   |   DPI: [bold {dpi_color}]{dpi_s}[/]"
            f"   |   Balance: [bold]{bal_s}[/]"
            f"   |   {datetime.now().strftime('%H:%M:%S')}"
        )
        self.query_one("#status-text", Label).update(text)


# ── Main App ────────────────────────────────────────────────────────────


class AgentManagerTUI(App):
    """Terminal dashboard for the Deterministic Agent Manager."""

    TITLE = "Agent Manager"
    CSS = """
    StatusBar { height: 3; background: $surface; padding: 0 1; }
    #status-text { padding: 1 0; }
    DataTable { height: 1fr; }
    TabPane { padding: 0; }
    .dpi-bar { height: 3; background: $surface; padding: 0 2; margin: 0 0 1 0; }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
        Binding("j", "focus_tab('jobs')", "Jobs"),
        Binding("a", "focus_tab('alerts')", "Alerts"),
        Binding("d", "focus_tab('dpi')", "DPI"),
        Binding("b", "focus_tab('balances')", "Balances"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar()
        with TabbedContent(initial="jobs"):
            with TabPane("Jobs", id="jobs"):
                yield DataTable(id="jobs-table")
            with TabPane("Alerts", id="alerts"):
                yield DataTable(id="alerts-table")
            with TabPane("DPI", id="dpi"):
                yield Static("", id="dpi-gauge")
                yield DataTable(id="dpi-table")
            with TabPane("Balances", id="balances"):
                yield DataTable(id="balances-table")
            with TabPane("Deposits", id="deposits"):
                yield DataTable(id="deposits-table")
            with TabPane("Articles", id="articles"):
                yield DataTable(id="articles-table")
            with TabPane("Cases", id="cases"):
                yield DataTable(id="cases-table")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
        self.action_refresh()
        self.set_interval(15, self.action_refresh)

    def _setup_tables(self) -> None:
        jobs_t = self.query_one("#jobs-table", DataTable)
        jobs_t.add_columns("ID", "Job", "Status", "Attempt", "Started", "Finished", "Error")

        alerts_t = self.query_one("#alerts-table", DataTable)
        alerts_t.add_columns("ID", "Rule", "Severity", "Message", "Created", "Ack")

        dpi_t = self.query_one("#dpi-table", DataTable)
        dpi_t.add_columns("ID", "Score", "Regularity", "Recency", "Trend", "Computed")

        bal_t = self.query_one("#balances-table", DataTable)
        bal_t.add_columns("ID", "Balance", "Recorded")

        dep_t = self.query_one("#deposits-table", DataTable)
        dep_t.add_columns("ID", "Amount", "Source", "Date", "Confirmed")

        art_t = self.query_one("#articles-table", DataTable)
        art_t.add_columns("ID", "Source", "Title", "Keywords", "Published")

        case_t = self.query_one("#cases-table", DataTable)
        case_t.add_columns("ID", "Case Name", "Details", "First Seen")

    def action_refresh(self) -> None:
        self.query_one(StatusBar).refresh_data()
        self._refresh_jobs()
        self._refresh_alerts()
        self._refresh_dpi()
        self._refresh_balances()
        self._refresh_deposits()
        self._refresh_articles()
        self._refresh_cases()

    def action_focus_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def _refresh_jobs(self) -> None:
        t = self.query_one("#jobs-table", DataTable)
        t.clear()
        for j in _query("SELECT * FROM job_runs ORDER BY id DESC LIMIT 50"):
            t.add_row(
                str(j["id"]), j["job_name"], j["status"],
                str(j["attempt"]), j.get("started_at", ""), j.get("finished_at", ""),
                (j.get("error_message") or "")[:60],
            )

    def _refresh_alerts(self) -> None:
        t = self.query_one("#alerts-table", DataTable)
        t.clear()
        for a in _query("SELECT * FROM alerts ORDER BY id DESC LIMIT 50"):
            t.add_row(
                str(a["id"]), a["rule_name"], a["severity"].upper(),
                a["message"][:80], a.get("created_at", ""),
                "Yes" if a["acknowledged"] else "No",
            )

    def _refresh_dpi(self) -> None:
        scores = _query("SELECT * FROM dpi_scores ORDER BY id DESC LIMIT 30")
        t = self.query_one("#dpi-table", DataTable)
        t.clear()

        gauge = self.query_one("#dpi-gauge", Static)
        if scores:
            latest = scores[0]
            s = latest["score"]
            bar_len = int(s * 40)
            color = "green" if s >= 0.7 else "yellow" if s >= 0.4 else "red"
            gauge.update(
                f"  DPI: [{color} bold]{s:.3f}[/]  "
                f"[{color}]{'#' * bar_len}[/][#333]{'.' * (40 - bar_len)}[/]  "
                f"regularity={latest['regularity']:.3f}  "
                f"recency={latest['recency']:.3f}  "
                f"trend={latest['trend']:.3f}"
            )
        else:
            gauge.update("  DPI: --- (no data)")

        for s in scores:
            t.add_row(
                str(s["id"]), f"{s['score']:.3f}", f"{s['regularity']:.3f}",
                f"{s['recency']:.3f}", f"{s['trend']:.3f}", s.get("computed_at", ""),
            )

    def _refresh_balances(self) -> None:
        t = self.query_one("#balances-table", DataTable)
        t.clear()
        for b in _query("SELECT * FROM fund_balances ORDER BY id DESC LIMIT 30"):
            t.add_row(str(b["id"]), _fmt_money(b["balance_amount"]), b.get("recorded_at", ""))

    def _refresh_deposits(self) -> None:
        t = self.query_one("#deposits-table", DataTable)
        t.clear()
        for d in _query("SELECT * FROM deposits ORDER BY id DESC LIMIT 50"):
            t.add_row(
                str(d["id"]), _fmt_money(d["amount"]),
                (d.get("source_posting") or "")[:40], d.get("deposit_date", ""),
                "Yes" if d["confirmed"] else "No",
            )

    def _refresh_articles(self) -> None:
        t = self.query_one("#articles-table", DataTable)
        t.clear()
        for a in _query("SELECT * FROM articles ORDER BY id DESC LIMIT 50"):
            t.add_row(
                str(a["id"]), a["source"].upper(),
                a["title"][:60], (a.get("keyword_hits") or "")[:30],
                a.get("published_date", ""),
            )

    def _refresh_cases(self) -> None:
        t = self.query_one("#cases-table", DataTable)
        t.clear()
        for c in _query("SELECT * FROM qualifying_cases ORDER BY id DESC LIMIT 50"):
            t.add_row(
                str(c["id"]), c["case_name"],
                (c.get("case_details") or "")[:60], c.get("first_seen_at", ""),
            )


def main():
    AgentManagerTUI().run()


if __name__ == "__main__":
    main()
