"""Simple logging setup used across the project."""
import logging
from config import LOG_LEVEL


def setup_logging():
    level_name = (LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    # Basic configuration for stdout
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


# Do NOT configure logging on import automatically; callers should call
# `setup_logging()` during application startup (CLI/server) to avoid
# side-effects during import (tests, library usage).
