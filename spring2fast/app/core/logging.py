"""Application logging configuration."""

import logging


def setup_logging() -> None:
    """Configure a simple application-wide logging setup."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
