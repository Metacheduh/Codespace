"""
Base job class for all deterministic jobs.

Each job:
  1. Receives a Database handle and its config section.
  2. Runs deterministic logic (fetch, parse, compute, compare).
  3. Writes results to SQLite.
  4. Never delegates decisions to an LLM.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import Any

from agent_manager.models import Database

logger = logging.getLogger(__name__)


class BaseJob(ABC):
    """Abstract base for all deterministic jobs."""

    name: str = ""

    def __init__(self, config: dict[str, Any], db: Database) -> None:
        self.config = config
        self.db = db

    @abstractmethod
    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        """Run the job's deterministic logic.

        Raises on failure so the manager can mark the run as failed.
        """

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
