"""
Shared constants for Liquid Glass Clipboard Manager.
Centralizes paths, defaults, and configuration to avoid DRY violations.
"""

from pathlib import Path

# ── Application Directories ─────────────────────────────────────
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "LiquidGlassClipboard"
LOG_DIR = APP_SUPPORT_DIR / "logs"

# ── File Paths ───────────────────────────────────────────────────
DB_FILE = APP_SUPPORT_DIR / "history.json"
SETTINGS_FILE = APP_SUPPORT_DIR / "settings.json"
LOG_FILE = LOG_DIR / "app.log"

# ── Application Metadata ────────────────────────────────────────
APP_NAME = "Liquid Glass Clipboard"
APP_VERSION = "1.1.0"

# ── Settings Defaults ───────────────────────────────────────────
SETTINGS_DEFAULTS = {
    "hotkey_modifiers": ["option"],
    "hotkey_key": "v",
    "blur_intensity": 20,
    "window_opacity": 0.92,
    "auto_trim_whitespace": True,
    "max_history": 50,
    "theme": "auto",  # "auto", "light", "dark"
}

# ── Allowed Settings Keys (whitelist for input validation) ──────
ALLOWED_SETTINGS_KEYS = frozenset(SETTINGS_DEFAULTS.keys())

# ── Limits ───────────────────────────────────────────────────────
MAX_CLIP_TEXT_LENGTH = 1_000_000  # 1 MB of text
MAX_HISTORY_LIMIT = 500
MIN_HISTORY_LIMIT = 10
MAX_ITEM_ID_LENGTH = 64

# ── Log Configuration ───────────────────────────────────────────
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 2
