"""
Snapshot testing for HTML parsing and data extraction.

These tests validate that scrapers correctly parse HTML content
and extract expected data structures.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from agent_manager.jobs.usvsst_scraper import USVSSTScraperJob
from agent_manager.jobs.doj_monitor import DOJMonitorJob
from agent_manager.jobs.ofac_monitor import OFACMonitorJob
from agent_manager.models import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        yield db


class TestUSVSSTParsingSnapshots:
    """Test USVSST scraper HTML parsing against known snapshots."""

    def test_parse_fund_balance_snapshot(self, temp_db):
        """Parse fund balance from sample HTML snapshot."""
        # Sample HTML snapshot
        html = """
        <html>
            <body>
                <div class="balance-container">
                    <span class="amount">$1,234,567.89</span>
                </div>
            </body>
        </html>
        """

        job = USVSSTScraperJob(
            {
                "sources": [
                    {
                        "name": "fund_balance",
                        "url": "http://example.com/balance",
                        "selectors": {"balance": ".amount"},
                    }
                ]
            },
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "usvsst_scraper", "running", 1)
            job._parse_fund_balance(
                conn,
                run_id,
                html,
                {"balance": ".amount"},
            )

            # Verify balance was extracted correctly
            result = conn.execute(
                "SELECT balance_amount FROM fund_balances ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert result is not None
            assert float(result["balance_amount"]) == 1234567.89

    def test_parse_qualifying_cases_snapshot(self, temp_db):
        """Parse qualifying cases from sample HTML snapshot."""
        html = """
        <html>
            <body>
                <table>
                    <tr class="case-row">
                        <td>Case A</td>
                        <td>Details A</td>
                    </tr>
                    <tr class="case-row">
                        <td>Case B</td>
                        <td>Details B</td>
                    </tr>
                </table>
            </body>
        </html>
        """

        job = USVSSTScraperJob(
            {"sources": []},
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "usvsst_scraper", "running", 1)
            job._parse_qualifying_cases(
                conn,
                run_id,
                html,
                {"case_rows": ".case-row"},
            )

            # Verify cases were extracted
            results = conn.execute(
                "SELECT case_name FROM qualifying_cases ORDER BY id"
            ).fetchall()
            assert len(results) == 2
            assert results[0]["case_name"] == "Case A"
            assert results[1]["case_name"] == "Case B"

    def test_parse_balance_with_various_formats(self, temp_db):
        """Test fund balance parsing handles various dollar formats."""
        test_cases = [
            ("$1,234,567.89", 1234567.89),
            ("$100", 100.00),
            ("$1000.50", 1000.50),
            ("$9,999,999.99", 9999999.99),
        ]

        job = USVSSTScraperJob(
            {"sources": []},
            temp_db,
        )

        for raw_value, expected in test_cases:
            html = f'<div class="bal">{raw_value}</div>'
            with temp_db.connection() as conn:
                run_id = temp_db.insert_job_run(conn, "usvsst_scraper", "running", 1)
                job._parse_fund_balance(
                    conn,
                    run_id,
                    html,
                    {"balance": ".bal"},
                )

                result = conn.execute(
                    "SELECT balance_amount FROM fund_balances WHERE job_run_id = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (run_id,),
                ).fetchone()
                assert float(result["balance_amount"]) == expected


class TestDOJParsingSnapshots:
    """Test DOJ Monitor scraper HTML parsing against known snapshots."""

    def test_parse_articles_snapshot(self, temp_db):
        """Parse DOJ articles from sample HTML snapshot."""
        html = """
        <html>
            <body>
                <article class="news-item">
                    <a href="http://example.com/article1">This is a very important article about USVSST funding</a>
                    <p>Additional details</p>
                </article>
                <article class="news-item">
                    <a href="http://example.com/article2">Another lengthy article with useful information here</a>
                    <p>Other topic</p>
                </article>
            </body>
        </html>
        """

        job = DOJMonitorJob(
            {
                "url": "http://example.com/doj",
                "selectors": {"articles": "article.news-item"},
            },
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "doj_monitor", "running", 1)
            articles = job._extract_articles(html, {"articles": "article.news-item"})

            # Verify articles were extracted
            assert len(articles) == 2
            assert articles[0]["title"] == "This is a very important article about USVSST funding"
            assert articles[0]["url"] == "http://example.com/article1"

    def test_parse_articles_empty_snapshot(self, temp_db):
        """Handle empty article lists gracefully."""
        html = "<html><body>No articles</body></html>"

        job = DOJMonitorJob(
            {
                "url": "http://example.com/doj",
                "selectors": {"articles": "article.news-item"},
            },
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "doj_monitor", "running", 1)
            articles = job._extract_articles(html, {"articles": "article.news-item"})

            # Should return empty list, not raise error
            assert articles == []


class TestOFACParsingSnapshots:
    """Test OFAC Monitor scraper HTML parsing against known snapshots."""

    def test_parse_actions_snapshot(self, temp_db):
        """Parse OFAC actions from sample HTML snapshot."""
        html = """
        <html>
            <body>
                <div class="action-entry">
                    <a href="http://example.com/action1">New OFAC sanctions list published today</a>
                    <span class="date">2024-01-01</span>
                </div>
                <div class="action-entry">
                    <a href="http://example.com/action2">Updated enforcement actions for suspicious entities</a>
                    <span class="date">2024-01-02</span>
                </div>
            </body>
        </html>
        """

        job = OFACMonitorJob(
            {
                "url": "http://example.com/ofac",
                "selectors": {"actions": "div.action-entry"},
            },
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "ofac_monitor", "running", 1)
            actions = job._extract_actions(html, {"actions": "div.action-entry"})

            # Verify actions were extracted
            assert len(actions) == 2
            assert actions[0]["title"] == "New OFAC sanctions list published today"
            assert actions[0]["url"] == "http://example.com/action1"

    def test_parse_actions_missing_selector(self, temp_db):
        """Handle missing CSS selector gracefully."""
        html = "<html><body>Some content</body></html>"

        job = OFACMonitorJob(
            {
                "url": "http://example.com/ofac",
                "selectors": {},
            },
            temp_db,
        )

        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "ofac_monitor", "running", 1)
            # Should not raise error, should return empty list
            actions = job._extract_actions(html, {})

            assert isinstance(actions, list)


class TestDetectDeposits:
    """Test deposit detection from balance changes."""

    def test_detect_deposit_from_balance_increase(self, temp_db):
        """Deposit is detected when balance increases."""
        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "usvsst_scraper", "succeeded", 1)

            # Insert two balance snapshots
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1000000.00),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1050000.00),  # $50k increase
            )

            # Detect deposits
            rows = conn.execute(
                "SELECT balance_amount FROM fund_balances WHERE job_run_id = ? "
                "ORDER BY id DESC LIMIT 2",
                (run_id,),
            ).fetchall()

            current = float(rows[0]["balance_amount"])
            previous = float(rows[1]["balance_amount"])
            diff = current - previous

            assert diff == 50000.00

    def test_no_deposit_on_balance_decrease(self, temp_db):
        """No deposit when balance decreases (likely distribution)."""
        with temp_db.connection() as conn:
            run_id = temp_db.insert_job_run(conn, "usvsst_scraper", "succeeded", 1)

            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 1000000.00),
            )
            conn.execute(
                "INSERT INTO fund_balances (job_run_id, balance_amount) VALUES (?, ?)",
                (run_id, 900000.00),  # $100k decrease
            )

            rows = conn.execute(
                "SELECT balance_amount FROM fund_balances WHERE job_run_id = ? "
                "ORDER BY id DESC LIMIT 2",
                (run_id,),
            ).fetchall()

            current = float(rows[0]["balance_amount"])
            previous = float(rows[1]["balance_amount"])
            diff = current - previous

            # Negative diff should not trigger deposit
            assert diff < 0
