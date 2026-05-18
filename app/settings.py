"""
Settings management for Liquid Glass Clipboard Manager.
Persists user preferences to a JSON file in ~/Library/Application Support/.
"""

import json
import os
from pathlib import Path


DEFAULTS = {
    "hotkey_modifiers": ["option"],
    "hotkey_key": "v",
    "blur_intensity": 20,
    "window_opacity": 0.92,
    "auto_trim_whitespace": True,
    "max_history": 50,
    "theme": "auto",  # "auto", "light", "dark"
}

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "LiquidGlassClipboard"
SETTINGS_FILE = APP_SUPPORT_DIR / "settings.json"


class Settings:
    """Thread-safe settings store backed by a JSON file."""

    def __init__(self):
        self._data: dict = {}
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        # Merge defaults for any missing keys
        for key, val in DEFAULTS.items():
            self._data.setdefault(key, val)
        self._save()

    def _save(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def get_all(self) -> dict:
        return dict(self._data)

    def update(self, data: dict):
        self._data.update(data)
        self._save()
