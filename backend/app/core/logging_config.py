"""Logging setup.

Phase 0 keeps this deliberately small: standard-library logging only, a single
stream handler, UTC timestamps. The secret-masking filter arrives in Phase 5
together with the PayPal client that could actually leak one.
"""

from __future__ import annotations

import logging
import time

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s.%(msecs)03dZ %(levelname)-8s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once, with UTC timestamps."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    formatter.converter = time.gmtime  # log in UTC, matching the API (R10)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    _CONFIGURED = True
