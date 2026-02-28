"""
Load testing for Agent Manager API using Locust.

Run with: locust -f load_test.py --host=http://localhost:8080

Tests:
- Dashboard homepage
- API status endpoint
- Job history endpoint
- Alert listing
- DPI scores
- CSV exports
- Rate limiting behavior
"""

from __future__ import annotations

from locust import HttpUser, task, between


class DashboardUser(HttpUser):
    """Simulates a user browsing the dashboard."""

    wait_time = between(1, 3)

    @task(3)
    def get_status(self):
        """Check system status - highest frequency."""
        self.client.get("/api/status")

    @task(2)
    def get_jobs(self):
        """View job history."""
        self.client.get("/api/jobs?limit=20")

    @task(2)
    def get_alerts(self):
        """View recent alerts."""
        self.client.get("/api/alerts?limit=20")

    @task(1)
    def get_dpi_scores(self):
        """View DPI trends."""
        self.client.get("/api/dpi?limit=30")

    @task(1)
    def get_balances(self):
        """View fund balance history."""
        self.client.get("/api/balances?limit=30")

    @task(1)
    def get_alert_analytics(self):
        """View alert analytics."""
        self.client.get("/api/alert-analytics")

    @task(1)
    def get_metrics(self):
        """Fetch Prometheus metrics."""
        self.client.get("/metrics")

    @task(1)
    def health_check(self):
        """Check service health."""
        self.client.get("/health")

    @task(1)
    def export_alerts_csv(self):
        """Export alerts as CSV."""
        self.client.get("/api/export/alerts")

    def on_start(self):
        """Called when a Locust user starts."""
        self.client.get("/")  # Load dashboard


class RateLimitTester(HttpUser):
    """Tests rate limiting behavior."""

    wait_time = between(0.1, 0.2)  # Faster requests to trigger rate limit

    @task
    def rapid_requests(self):
        """Make rapid requests to test rate limiting."""
        response = self.client.get("/api/status")
        # Rate limiter should return 429 after 100 requests/minute
        if response.status_code == 429:
            print("Rate limit triggered as expected")
