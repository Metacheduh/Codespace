"""
DAG-based job dependency resolution.

Jobs declare their upstream dependencies in config.yaml via `depends_on`.
The DAG enforces that a job only runs when ALL of its dependencies have
succeeded in the current scheduling cycle.

This module is purely deterministic — no LLM involvement.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Sequence


class CyclicDependencyError(Exception):
    """Raised when the job dependency graph contains a cycle."""


class MissingDependencyError(Exception):
    """Raised when a job depends on an undefined job."""


class JobDAG:
    """Directed acyclic graph of job dependencies."""

    def __init__(self) -> None:
        self._edges: dict[str, list[str]] = defaultdict(list)  # child → parents
        self._all_jobs: set[str] = set()

    def add_job(self, job_name: str, depends_on: Sequence[str] | None = None) -> None:
        self._all_jobs.add(job_name)
        if depends_on:
            for dep in depends_on:
                self._edges[job_name].append(dep)
                self._all_jobs.add(dep)

    def validate(self) -> None:
        """Validate: no cycles, no missing deps."""
        for job, deps in self._edges.items():
            for dep in deps:
                if dep not in self._all_jobs:
                    raise MissingDependencyError(
                        f"Job {job!r} depends on undefined job {dep!r}"
                    )
        if self._has_cycle():
            raise CyclicDependencyError("Job dependency graph contains a cycle")

    def _has_cycle(self) -> bool:
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for parent in self._edges.get(node, []):
                if parent not in visited:
                    if dfs(parent):
                        return True
                elif parent in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for job in self._all_jobs:
            if job not in visited:
                if dfs(job):
                    return True
        return False

    def topological_order(self) -> list[str]:
        """Return jobs in execution order (dependencies first)."""
        self.validate()
        in_degree: dict[str, int] = {j: 0 for j in self._all_jobs}
        # Build forward edges: parent → children
        forward: dict[str, list[str]] = defaultdict(list)
        for child, parents in self._edges.items():
            for parent in parents:
                forward[parent].append(child)
                in_degree[child] += 1

        queue: deque[str] = deque(j for j, d in in_degree.items() if d == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for child in forward.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return order

    def get_dependencies(self, job_name: str) -> list[str]:
        """Return direct dependencies (parents) of a job."""
        return list(self._edges.get(job_name, []))

    def is_ready(self, job_name: str, succeeded_jobs: set[str]) -> bool:
        """Return True if all dependencies of job_name have succeeded."""
        deps = self._edges.get(job_name, [])
        return all(dep in succeeded_jobs for dep in deps)
