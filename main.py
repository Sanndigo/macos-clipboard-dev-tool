"""
Liquid Glass Clipboard Manager — Main Entry Point
Launches the pywebview window, clipboard monitor, and global hotkey listener.
"""

import json
import os
import sys
import threading
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.logging_config import get_logger
from app.constants import APP_SUPPORT_DIR

logger = get_logger("main")

# ── Crash handler using the centralized logger ──────────────────
def _log_crash(exc_type, exc_value, exc_tb):
    import traceback
    logger.critical(
        "Unhandled exception:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )

sys.excepthook = _log_crash


import webview

from app.settings import Settings
from app.database import ClipboardDatabase
from app.clipboard_monitor import ClipboardMonitor
from app.api_bridge import ApiBridge
from app.hotkey_manager import HotkeyManager


def get_ui_path() -> str:
    """Resolve the path to ui/index.html, works both in dev and PyInstaller bundle."""
    if getattr(sys, '_MEIPASS', None):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'ui', 'index.html')


from Foundation import NSObject

class _MenuInjector(NSObject):
    """Injects a standard macOS Edit menu so Cmd+C/V/X work in the webview."""

    def injectMenu_(self, arg):
        try:
            from AppKit import NSApp, NSMenu, NSMenuItem
            main_menu = NSMenu.alloc().init()
            app_menu_item = NSMenuItem.alloc().init()
            main_menu.addItem_(app_menu_item)

            edit_menu_item = NSMenuItem.alloc().init()
            edit_menu_item.setTitle_("Edit")
            edit_menu = NSMenu.alloc().initWithTitle_("Edit")

            edit_menu.addItemWithTitle_action_keyEquivalent_("Undo", "undo:", "z")
            edit_menu.addItemWithTitle_action_keyEquivalent_("Redo", "redo:", "Z")
            edit_menu.addItem_(NSMenuItem.separatorItem())
            edit_menu.addItemWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
            edit_menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
            edit_menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
            edit_menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")

            edit_menu_item.setSubmenu_(edit_menu)
            main_menu.addItem_(edit_menu_item)
            NSApp.setMainMenu_(main_menu)
            logger.info("✓ Successfully injected macOS main menu")
        except Exception as e:
            logger.error("Failed to inject macOS menu: %s", e)

    def activateApp_(self, arg):
        try:
            from AppKit import NSApp
            NSApp.activateIgnoringOtherApps_(True)
        except Exception as e:
            logger.error("Failed to activate app: %s", e)

_menu_injector = _MenuInjector.alloc().init()


def _item_to_js(item: dict) -> str:
    """Serialize a clip item to a JS-safe JSON string."""
    safe = dict(item)
    text = safe.get("text", "")
    safe["preview"] = text[:200] if len(text) > 200 else text
    return json.dumps(safe, ensure_ascii=False)


def main():
    logger.info("--- APP STARTED --- Home: %s", Path.home())

    try:
        # ── Initialize core components ──────────────────────────
        settings = Settings()
        db = ClipboardDatabase(max_items=settings.get("max_history", 50))
        logger.info("Loaded %d items from DB", len(db.get_all()))
        api = ApiBridge(db=db, settings=settings)
    except Exception as e:
        logger.critical("Error during init: %s", e, exc_info=True)
        return

    # ── Create pywebview window ─────────────────────────────
    ui_path = get_ui_path()
    window = webview.create_window(
        title='Liquid Glass Clipboard',
        url=ui_path,
        width=520,
        height=620,
        resizable=True,
        frameless=True,
        easy_drag=False,    # We handle drag via CSS -webkit-app-region
        transparent=True,
        on_top=True,
        js_api=api,
        min_size=(400, 400),
    )

    api.set_window(window)

    # ── Clipboard monitor callback ──────────────────────────
    def on_new_clip(text: str):
        auto_trim = settings.get("auto_trim_whitespace", True)
        item = db.add(text, auto_trim=auto_trim)
        if item:
            try:
                window.evaluate_js(f"App.onNewClip({_item_to_js(item)})")
            except Exception:
                pass  # Window might not be ready yet

    # ── Visibility state tracking ───────────────────────────
    _visibility_lock = threading.Lock()
    is_visible = True

    def set_invisible():
        nonlocal is_visible
        with _visibility_lock:
            is_visible = False

    api.on_hide_callback = set_invisible

    # ── Start clipboard monitor ─────────────────────────────
    monitor = ClipboardMonitor(on_new_clip=on_new_clip, poll_interval=0.5)

    # ── Hotkey toggle (debounced, single-threaded) ──────────
    _toggle_pending = threading.Event()

    def toggle_window():
        nonlocal is_visible
        try:
            with _visibility_lock:
                current_visible = is_visible

            logger.debug("toggle_window called. is_visible=%s", current_visible)

            if not current_visible:
                window.restore()
                window.show()
                window.on_top = True
                with _visibility_lock:
                    is_visible = True

                # Bring app to front safely on the main thread
                _menu_injector.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "activateApp:", None, False
                )

                # Refresh history and focus search
                window.evaluate_js("App.loadHistory()")
                window.evaluate_js(
                    "setTimeout(() => { const input = document.getElementById('search-input'); "
                    "if (input) input.focus(); }, 100);"
                )
            else:
                window.minimize()
                with _visibility_lock:
                    is_visible = False
        except Exception as e:
            logger.error("Toggle error: %s", e)

    def _toggle_worker():
        """Single background thread that services toggle requests."""
        while True:
            _toggle_pending.wait()
            _toggle_pending.clear()
            toggle_window()

    _toggle_thread = threading.Thread(target=_toggle_worker, daemon=True, name="toggle-worker")
    _toggle_thread.start()

    def async_toggle_window():
        """Signal the toggle worker instead of spawning a new thread each time."""
        logger.debug("CGEventTap triggered hotkey!")
        _toggle_pending.set()

    hotkey = HotkeyManager(
        modifiers=settings.get("hotkey_modifiers", ["option"]),
        key=settings.get("hotkey_key", "v"),
        callback=async_toggle_window,
    )

    def on_settings_changed(new_settings):
        mods = new_settings.get("hotkey_modifiers", ["option"])
        key = new_settings.get("hotkey_key", "v")
        hotkey.update_hotkey(mods, key)

    api.on_settings_changed_callback = on_settings_changed

    # ── Start services after webview is ready ───────────────
    def on_loaded():
        monitor.start()
        hotkey.start()

        # Inject standard macOS Edit menu
        _menu_injector.performSelectorOnMainThread_withObject_waitUntilDone_(
            "injectMenu:", None, False
        )

        # Bring app to front initially
        _menu_injector.performSelectorOnMainThread_withObject_waitUntilDone_(
            "activateApp:", None, False
        )

        # Auto-focus input initially
        window.evaluate_js(
            "setTimeout(() => { const input = document.getElementById('search-input'); "
            "if (input) input.focus(); }, 100);"
        )
        logger.info("✅ Liquid Glass Clipboard Manager is running")
        logger.info("   Press ⌥V to show/hide")

    # ── Window events ───────────────────────────────────────
    def on_closing():
        monitor.stop()
        hotkey.stop()

    window.events.loaded += on_loaded
    window.events.closing += on_closing

    # ── Start webview (blocks on main thread) ───────────────
    webview.start(
        debug=('--debug' in sys.argv),
        gui='cocoa',
    )


if __name__ == '__main__':
    main()
