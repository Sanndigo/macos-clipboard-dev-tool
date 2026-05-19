"""
Settings management for Liquid Glass Clipboard Manager.
Persists user preferences to a JSON file in ~/Library/Application Support/.

Thread-safe: all public methods are guarded by a reentrant lock.
File writes use atomic rename to prevent corruption on crash.
"""

import json
import os
import tempfile
import threading
from typing import Any, Optional

from app.constants import (
    APP_SUPPORT_DIR,
    SETTINGS_FILE,
    SETTINGS_DEFAULTS,
    ALLOWED_SETTINGS_KEYS,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


class Settings:
    """Thread-safe settings store backed by a JSON file."""

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.RLock()
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load settings from disk and merge with defaults."""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = data
                else:
                    logger.warning("Settings file contained non-dict data; resetting.")
                    self._data = {}
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.error("Failed to load settings: %s", e)
                self._data = {}

        # Merge defaults for any missing keys
        for key, val in SETTINGS_DEFAULTS.items():
            self._data.setdefault(key, val)

        self._save()

    def _save(self):
        """Atomically write settings to disk. Must be called with lock held (or from _load)."""
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(APP_SUPPORT_DIR), suffix=".tmp", prefix="settings_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)

                os.replace(tmp_path, str(SETTINGS_FILE))
                os.chmod(str(SETTINGS_FILE), 0o600)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error("Failed to save settings: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a single setting value.

        Returns True if the key is allowed and was set, False otherwise.
        Only keys in ALLOWED_SETTINGS_KEYS are accepted.
        """
        if key not in ALLOWED_SETTINGS_KEYS:
            logger.warning("Rejected unknown settings key: %s", key)
            return False

        with self._lock:
            self._data[key] = value
            self._save()
            return True

    def get_all(self) -> dict:
        """Return a copy of all settings."""
        with self._lock:
            return dict(self._data)

    def update(self, data: dict):
        """Update multiple settings at once. Only allowed keys are accepted."""
        with self._lock:
            for key, value in data.items():
                if key in ALLOWED_SETTINGS_KEYS:
                    self._data[key] = value
                else:
                    logger.warning("Rejected unknown settings key: %s", key)
            self._save()
