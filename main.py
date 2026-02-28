#!/usr/bin/env python3
"""
Entry point for the Deterministic Agent Manager.

Run this script manually to test, or let launchd run it every minute.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from agent_manager.manager import AgentManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".agent_manager" / "agent_manager.log"),
        logging.StreamHandler(sys.stdout),
    ],
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
