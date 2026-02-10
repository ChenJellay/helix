"""Metrics integration client (stub).

In production this would connect to Prometheus, Grafana, DataDog, or similar.
For the thin-slice MVP, we return mock data.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


class MetricsClient:
    """Stub metrics client for CI/CD and production metrics.

    Replace with real integrations (Prometheus, Grafana, DataDog)
    in a production deployment.
    """

    async def get_project_metrics(self, repo_or_project: str) -> dict[str, Any]:
        """Get CI/CD and performance metrics for a project.

        Args:
            repo_or_project: Repository URL or project identifier.

        Returns:
            Dict of metric_name -> value.
        """
        logger.info("Fetching metrics for %s (stub)", repo_or_project)

        # Stub: return realistic-looking mock data
        return {
            "test_coverage": f"{random.randint(60, 95)}%",
            "p50_latency_ms": f"{random.randint(50, 200)}ms",
            "p99_latency_ms": f"{random.randint(200, 1000)}ms",
            "error_rate": f"{random.uniform(0.01, 2.0):.2f}%",
            "deployment_frequency": f"{random.randint(1, 10)}/week",
            "ci_pass_rate": f"{random.randint(85, 100)}%",
            "open_bugs": str(random.randint(0, 20)),
        }

    async def get_metric_value(
        self, repo_or_project: str, metric_name: str
    ) -> str | None:
        """Get a specific metric value.

        Args:
            repo_or_project: Repository URL or project identifier.
            metric_name: Name of the metric to fetch.

        Returns:
            The metric value as a string, or None if not available.
        """
        logger.info("Fetching metric '%s' for %s (stub)", metric_name, repo_or_project)

        # Stub: return mock values based on common metric names
        mock_values = {
            "latency_reduction": str(random.randint(5, 25)),
            "error_rate": f"{random.uniform(0.1, 5.0):.2f}",
            "user_adoption": str(random.randint(10, 80)),
            "throughput": str(random.randint(100, 10000)),
            "availability": f"{random.uniform(99.0, 99.99):.2f}",
        }

        # Try exact match first, then partial
        if metric_name in mock_values:
            return mock_values[metric_name]

        for key, value in mock_values.items():
            if key in metric_name.lower():
                return value

        return str(random.randint(1, 100))
