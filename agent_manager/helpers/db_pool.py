"""
Simple connection pool for SQLite.

SQLite handles concurrent access reasonably well with WAL mode,
but creating/closing connections repeatedly is wasteful.
This pool maintains a small number of reusable connections.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from queue import LifoQueue, Empty
from typing import Iterator

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """Simple LIFO connection pool for SQLite."""

    def __init__(
        self,
        db_path: str | Path,
        pool_size: int = 5,
        timeout: float = 5.0,
    ) -> None:
        self.db_path = str(db_path)
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: LifoQueue[sqlite3.Connection] = LifoQueue(maxsize=pool_size)
        self._created = 0

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with standard settings."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._created += 1
        logger.debug("Created DB connection %d", self._created)
        return conn

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a connection from the pool."""
        conn: sqlite3.Connection | None = None
        try:
            # Try to get an existing connection from the pool
            conn = self._pool.get(block=False)
            logger.debug("Reused pooled connection")
        except Empty:
            # No pooled connections available, create a new one
            conn = self._create_connection()

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            # Return the connection to the pool if there's space
            try:
                self._pool.put(conn, block=False)
                logger.debug("Returned connection to pool")
            except Exception:
                # Pool is full, close the connection
                logger.debug("Pool full, closing connection")
                conn.close()

    def close_all(self) -> None:
        """Close all pooled connections."""
        while True:
            try:
                conn = self._pool.get(block=False)
                conn.close()
            except Empty:
                break
        logger.info("Closed all pooled connections")

    def get_pool_status(self) -> dict:
        """Return pool statistics."""
        return {
            "pool_size": self.pool_size,
            "queued_connections": self._pool.qsize(),
            "total_created": self._created,
        }
