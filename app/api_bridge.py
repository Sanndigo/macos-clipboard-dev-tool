"""
pywebview API Bridge for Liquid Glass Clipboard Manager.
Exposes Python methods to the JavaScript frontend via window.pywebview.api.

All inputs are validated before processing. Public methods return defensive
copies to prevent mutation of internal state.
"""

from AppKit import NSPasteboard, NSStringPboardType

from app.constants import APP_NAME, APP_VERSION, MAX_ITEM_ID_LENGTH, ALLOWED_SETTINGS_KEYS
from app.database import ClipboardDatabase
from app.settings import Settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def _validate_item_id(item_id) -> str | None:
    """Validate and return item_id, or None if invalid."""
    if not isinstance(item_id, str):
        return None
    item_id = item_id.strip()
    if not item_id or len(item_id) > MAX_ITEM_ID_LENGTH:
        return None
    return item_id


class ApiBridge:
    """Bridge between the JS frontend and the Python backend.

    All public methods are automatically exposed to JavaScript
    via pywebview's JS API binding.
    """

    def __init__(self, db: ClipboardDatabase, settings: Settings):
        self._db = db
        self._settings = settings
        self._window = None  # Set after window creation
        self.on_hide_callback = None  # Settable by main.py
        self.on_settings_changed_callback = None  # Settable by main.py

    def set_window(self, window):
        self._window = window

    # ── Clipboard History ─────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return all clipboard items, newest first.

        Returns defensive copies with truncated preview text.
        """
        items = self._db.get_all()  # Already returns copies
        for item in items:
            # Add truncated preview for the list view
            text = item.get("text", "")
            item["preview"] = text[:200] if len(text) > 200 else text
        return items

    def get_item(self, item_id: str) -> dict | None:
        """Get a single item by ID."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return None
        return self._db.get_by_id(validated)

    def delete_item(self, item_id: str) -> bool:
        """Delete an item from history."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return False
        return self._db.delete(validated)

    def toggle_pin(self, item_id: str) -> dict | None:
        """Toggle pin status for an item."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return None
        return self._db.toggle_pin(validated)

    def clear_history(self) -> bool:
        """Clear all history."""
        self._db.clear()
        return True

    # ── Editor ────────────────────────────────────────────────────

    def update_item_text(self, item_id: str, new_text: str) -> dict | None:
        """Update the text of a clipboard item (from the editor)."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return None
        if not isinstance(new_text, str) or not new_text.strip():
            return None
        return self._db.update_text(validated, new_text)

    # ── Paste Action ──────────────────────────────────────────────

    def paste_item(self, item_id: str) -> bool:
        """Copy item to system clipboard."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return False

        item = self._db.get_by_id(validated)
        if not item:
            return False

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(item["text"], NSStringPboardType)
        return True

    def copy_item(self, item_id: str) -> bool:
        """Copy item to system clipboard without pasting."""
        validated = _validate_item_id(item_id)
        if validated is None:
            return False

        item = self._db.get_by_id(validated)
        if not item:
            return False

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(item["text"], NSStringPboardType)
        return True

    # ── Settings ──────────────────────────────────────────────────

    def get_settings(self) -> dict:
        """Return all settings."""
        return self._settings.get_all()

    def update_settings(self, updates: dict) -> dict:
        """Update settings and return the new settings dict.

        Only whitelisted keys are accepted; unknown keys are silently ignored.
        """
        if not isinstance(updates, dict):
            return self._settings.get_all()

        # Filter to allowed keys only
        safe_updates = {k: v for k, v in updates.items() if k in ALLOWED_SETTINGS_KEYS}
        for k, v in safe_updates.items():
            self._settings.set(k, v)

        if self.on_settings_changed_callback:
            self.on_settings_changed_callback(self._settings.get_all())

        return self._settings.get_all()

    # ── Window Control ────────────────────────────────────────────

    def hide_window(self):
        """Minimize the application window."""
        if self._window:
            self._window.minimize()
        if self.on_hide_callback:
            self.on_hide_callback()

    def get_app_info(self) -> dict:
        """Return app metadata."""
        return {
            "name": APP_NAME,
            "version": APP_VERSION,
            "author": "Developer",
        }