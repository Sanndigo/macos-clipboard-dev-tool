"""
Liquid Glass Clipboard Manager — Main Entry Point
Launches the pywebview window, clipboard monitor, and global hotkey listener.
"""

import os
import sys
import threading
import webview

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


def main():
    # ── Initialize core components ──────────────────────────
    settings = Settings()
    db = ClipboardDatabase(max_items=settings.get("max_history", 50))
    api = ApiBridge(db=db, settings=settings)

    # Dock Icon is visible by default. (Removed LSUIElement stealth mode)

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
            # Push to UI via JS evaluation
            try:
                window.evaluate_js(f"App.onNewClip({__item_to_js(item)})")
            except Exception:
                pass  # Window might not be ready yet

    def __item_to_js(item: dict) -> str:
        """Serialize a clip item to a JS-safe JSON string."""
        import json
        safe = dict(item)
        safe["preview"] = safe["text"][:200] if len(safe["text"]) > 200 else safe["text"]
        return json.dumps(safe, ensure_ascii=False)

    # ── Visibility state tracking ───────────────────────────
    is_visible = True

    def set_invisible():
        nonlocal is_visible
        is_visible = False

    api.on_hide_callback = set_invisible

    # ── Start clipboard monitor ─────────────────────────────
    monitor = ClipboardMonitor(on_new_clip=on_new_clip, poll_interval=0.5)

    # ── Hotkey toggle ───────────────────────────────────────
    def toggle_window():
        nonlocal is_visible
        try:
            if not is_visible:
                window.restore()
                window.show()
                window.on_top = True
                is_visible = True
                # Bring app to front
                try:
                    from AppKit import NSApp
                    NSApp.activateIgnoringOtherApps_(True)
                except Exception:
                    pass
                # Refresh history
                window.evaluate_js("App.loadHistory()")
                # Focus the search input
                window.evaluate_js("setTimeout(() => { const input = document.getElementById('search-input'); if (input) input.focus(); }, 100);")
            else:
                window.minimize()
                is_visible = False
        except Exception as e:
            print(f"Toggle error: {e}")

    hotkey = HotkeyManager(
        modifiers=settings.get("hotkey_modifiers", ["option"]),
        key=settings.get("hotkey_key", "v"),
        callback=toggle_window,
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
        
        # Inject standard macOS Edit menu so Cmd+C/V/X and global hotkeys work properly
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
        except Exception as e:
            print(f"Failed to inject macOS menu: {e}")

        # Bring app to front initially
        try:
            from AppKit import NSApp
            NSApp.activateIgnoringOtherApps_(True)
        except Exception:
            pass
        # Auto-focus input initially
        window.evaluate_js("setTimeout(() => { const input = document.getElementById('search-input'); if (input) input.focus(); }, 100);")
        print("✅ Liquid Glass Clipboard Manager is running")
        print("   Press ⌥V to show/hide • Runs in background (no Dock icon)")

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
