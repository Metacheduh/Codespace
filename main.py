#!/usr/bin/env python3
"""
Entry point for the Deterministic Agent Manager.

Run this script manually to test, or let launchd run it every minute.
"""

import logging
import sys
from pathlib import Path

from agent_manager.helpers.logging_config import setup_logging
from agent_manager.manager import AgentManager

# Configure structured JSON logging
setup_logging(
    log_file=Path.home() / ".agent_manager" / "agent_manager.log",
    level=logging.INFO,
    json_format=True,
)
logger = logging.getLogger(__name__)


def main():
    """Run a single tick of the Agent Manager."""
    config_path = Path(__file__).parent / "config.yaml"

    try:
        manager = AgentManager(config_path)
        executed = manager.tick()

        if executed:
            logger.info("Tick completed: executed %s", executed)
        else:
            logger.debug("Tick completed: no jobs due")

        return 0
    except Exception as e:
        logger.error("Tick failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
