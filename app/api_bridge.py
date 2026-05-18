"""
pywebview API Bridge for Liquid Glass Clipboard Manager.
Exposes Python methods to the JavaScript frontend via window.pywebview.api.
"""

import time
import subprocess

from AppKit import NSPasteboard, NSStringPboardType

from app.database import ClipboardDatabase
from app.settings import Settings


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

    def set_window(self, window):
        self._window = window

    # ── Clipboard History ─────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return all clipboard items, newest first."""
        items = self._db.get_all()
        for item in items:
            # Truncate preview text for the list view
            item["preview"] = item["text"][:200] if len(item["text"]) > 200 else item["text"]
        return items

    def get_item(self, item_id: str) -> dict | None:
        """Get a single item by ID."""
        return self._db.get_by_id(item_id)

    def delete_item(self, item_id: str) -> bool:
        """Delete an item from history."""
        return self._db.delete(item_id)

    def toggle_pin(self, item_id: str) -> dict | None:
        """Toggle pin status for an item."""
        return self._db.toggle_pin(item_id)

    def clear_history(self) -> bool:
        """Clear all history."""
        self._db.clear()
        return True

    # ── Editor ────────────────────────────────────────────────────

    def update_item_text(self, item_id: str, new_text: str) -> dict | None:
        """Update the text of a clipboard item (from the editor)."""
        return self._db.update_text(item_id, new_text)

    # ── Paste Action ──────────────────────────────────────────────

    def paste_item(self, item_id: str) -> bool:
        """Copy item to system clipboard, hide window, and simulate Cmd+V."""
        item = self._db.get_by_id(item_id)
        if not item:
            return False

        # Write to system clipboard
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(item["text"], NSStringPboardType)

        # We no longer minimize the window here per user request.
        # However, because the window remains open and focused, simulating Cmd+V
        # would paste the text into our own search bar! So we disable the auto-paste.
        # subprocess.Popen([
        #     "osascript", "-e",
        #     'tell application "System Events" to keystroke "v" using command down'
        # ])

        return True

    def copy_item(self, item_id: str) -> bool:
        """Copy item to system clipboard without pasting."""
        item = self._db.get_by_id(item_id)
        if not item:
            return False

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(item["text"], NSStringPboardType)

        # Window remains open per user request
        return True

    # ── Settings ──────────────────────────────────────────────────

    def get_settings(self) -> dict:
        """Return all settings."""
        return self._settings.get_all()

    def update_settings(self, updates: dict):
        """Update settings and return the new settings dict."""
        for k, v in updates.items():
            self._settings.set(k, v)
        if getattr(self, 'on_settings_changed_callback', None):
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
            "name": "Liquid Glass Clipboard",
            "version": "1.0.0",
            "author": "Developer",
        }