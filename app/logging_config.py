"""
Centralized logging for Liquid Glass Clipboard Manager.
Logs are written to ~/Library/Application Support/LiquidGlassClipboard/logs/
with automatic rotation to prevent unbounded growth.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from app.constants import LOG_DIR, LOG_FILE, MAX_LOG_SIZE_BYTES, LOG_BACKUP_COUNT

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Configure Root Logger ───────────────────────────────────────
_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = RotatingFileHandler(
    str(LOG_FILE),
    maxBytes=MAX_LOG_SIZE_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)
_file_handler.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_console_handler.setLevel(logging.INFO)

# ── Set restrictive file permissions (owner-only read/write) ────
try:
    os.chmod(str(LOG_FILE), 0o600)
except OSError:
    pass  # File may not exist yet on first launch


def get_logger(name: str) -> logging.Logger:
    """Create a named logger with file and console handlers."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
        logger.setLevel(logging.DEBUG)
    return logger
