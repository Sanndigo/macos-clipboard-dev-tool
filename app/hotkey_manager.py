"""
Global hotkey manager for Liquid Glass Clipboard Manager.
Uses PyObjC CGEvent tap to intercept key events system-wide.
Requires Accessibility permissions on macOS.
"""

import threading
import time

from Quartz import (
    CGEventTapCreate,
    CGEventGetIntegerValueField,
    CGEventGetFlags,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventKeyDown,
    kCGKeyboardEventKeycode,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskControl,
    CFMachPortCreateRunLoopSource,
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    kCFRunLoopCommonModes,
    CFMachPortInvalidate,
)

from app.logging_config import get_logger

logger = get_logger(__name__)

# macOS virtual keycodes
KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C,
    "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11, "1": 0x12,
    "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19,
    "7": 0x1A, "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22,
    "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D, "m": 0x2E,
    "space": 0x31, "return": 0x24, "tab": 0x30, "escape": 0x35,
    "minus": 0x1B, "equal": 0x18, "bracketleft": 0x21, "bracketright": 0x1E,
    "backslash": 0x2A, "semicolon": 0x29, "quote": 0x27, "comma": 0x2B,
    "period": 0x2F, "slash": 0x2C, "grave": 0x32,
}

MODIFIER_FLAGS = {
    "command": kCGEventFlagMaskCommand,
    "cmd": kCGEventFlagMaskCommand,
    "option": kCGEventFlagMaskAlternate,
    "alt": kCGEventFlagMaskAlternate,
    "shift": kCGEventFlagMaskShift,
    "control": kCGEventFlagMaskControl,
    "ctrl": kCGEventFlagMaskControl,
}

MODIFIER_MASK = (
    kCGEventFlagMaskCommand
    | kCGEventFlagMaskAlternate
    | kCGEventFlagMaskShift
    | kCGEventFlagMaskControl
)


class HotkeyManager:
    """Registers a global hotkey via CGEvent tap.

    The CGEventTap is created ONCE and never restarted.
    Hotkey changes are handled by atomically swapping the target key/modifiers
    inside the already-running tap callback via a threading.Lock.
    This preserves the Accessibility permission grant across hotkey changes.
    """

    # Maximum retry attempts for CGEventTap creation
    _MAX_RETRY_ATTEMPTS = 60  # 2 minutes at 2s intervals

    def __init__(self, modifiers: list[str], key: str, callback, on_global_action=None):
        self._lock = threading.Lock()
        self._modifiers = list(modifiers)
        self._key = key
        self._callback = callback
        self._on_global_action = on_global_action
        self._thread: threading.Thread | None = None
        self._run_loop = None
        self._running = False
        
        self._typing_count = 0
        self._last_typing_time = 0.0

    def _compute_target_flags(self) -> int:
        """Must be called with self._lock held."""
        flags = 0
        for mod in self._modifiers:
            flag = MODIFIER_FLAGS.get(mod.lower())
            if flag:
                flags |= flag
        return flags

    def _event_callback(self, proxy, event_type, event, refcon):
        try:
            if event_type != kCGEventKeyDown:
                return event

            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            flags = CGEventGetFlags(event)
            active_mods = flags & MODIFIER_MASK

            with self._lock:
                target_keycode = KEYCODES.get(self._key.lower())
                target_flags = self._compute_target_flags()

            # Check if it's the main toggle hotkey (swallowed)
            if target_keycode is not None and keycode == target_keycode and active_mods == target_flags:
                self._callback()
                return None  # Swallow the event

            # Check for global actions (Cmd+C: 0x08, Cmd+V: 0x09, Cmd+X: 0x07)
            if active_mods == kCGEventFlagMaskCommand and keycode in (0x08, 0x09, 0x07):
                if self._on_global_action:
                    self._on_global_action()
                return event

            # Handle typing combo (only if no Cmd/Ctrl/Opt modifiers to avoid triggering on random shortcuts)
            if not (active_mods & (kCGEventFlagMaskCommand | kCGEventFlagMaskControl | kCGEventFlagMaskAlternate)):
                now = time.time()
                if now - self._last_typing_time > 2.0:
                    self._typing_count = 0
                
                self._last_typing_time = now
                self._typing_count += 1
                
                if self._typing_count >= 30:
                    self._typing_count = 0
                    if self._on_global_action:
                        self._on_global_action()

        except Exception as e:
            logger.error("Error in event callback: %s", e, exc_info=True)

        return event

    def start(self):
        """Start the hotkey listener in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey-listener")
        self._thread.start()

    def _run(self):
        """Run loop: retry creating CGEventTap until success or stopped."""
        tap = None
        attempt = 0

        while self._running and tap is None and attempt < self._MAX_RETRY_ATTEMPTS:
            attempt += 1
            try:
                tap = CGEventTapCreate(
                    kCGSessionEventTap,
                    kCGHeadInsertEventTap,
                    0,  # active tap
                    (1 << kCGEventKeyDown),
                    self._event_callback,
                    None,
                )
            except Exception as e:
                logger.error("CGEventTapCreate exception (attempt %d): %s", attempt, e)
                tap = None

            if tap is None:
                logger.info(
                    "Tap not created (attempt %d/%d) — Accessibility not granted? Retrying in 2s...",
                    attempt, self._MAX_RETRY_ATTEMPTS,
                )
                time.sleep(2)
            else:
                logger.info("✓ CGEventTap created on attempt %d", attempt)

        if not self._running:
            return

        if tap is None:
            logger.error(
                "Failed to create CGEventTap after %d attempts. "
                "Please grant Accessibility permissions.", self._MAX_RETRY_ATTEMPTS
            )
            return

        try:
            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            self._run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._run_loop, source, kCFRunLoopCommonModes)
            CFRunLoopRun()
            CFMachPortInvalidate(tap)
            logger.info("CGEventTap run loop exited")
        except Exception as e:
            logger.error("Error in hotkey run loop: %s", e, exc_info=True)

    def stop(self):
        """Stop the hotkey listener."""
        self._running = False
        if self._run_loop:
            CFRunLoopStop(self._run_loop)
            self._run_loop = None

    def update_hotkey(self, modifiers: list[str], key: str):
        """Update the hotkey WITHOUT restarting the CGEventTap.

        Atomically swaps the modifiers/key inside the lock so the live
        tap immediately starts matching the new combination.
        Accessibility permissions are fully preserved.
        """
        logger.info("Updating hotkey to %s + %s", modifiers, key)
        with self._lock:
            self._modifiers = list(modifiers)
            self._key = key
        logger.info("Hotkey updated (tap alive): %s + %s", modifiers, key)
