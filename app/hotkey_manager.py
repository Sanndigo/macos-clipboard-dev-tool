"""
Global hotkey manager for Liquid Glass Clipboard Manager.
Uses PyObjC CGEvent tap to intercept key events system-wide.
Requires Accessibility permissions on macOS.
"""

import threading
import traceback

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
)

# macOS virtual keycodes
KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C,
    "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11, "1": 0x12,
    "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19,
    "7": 0x1A, "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22,
    "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D, "m": 0x2E,
    "space": 0x31, "return": 0x24, "tab": 0x30, "escape": 0x35,
}

MODIFIER_FLAGS = {
    "command": kCGEventFlagMaskCommand,
    "option": kCGEventFlagMaskAlternate,
    "shift": kCGEventFlagMaskShift,
    "control": kCGEventFlagMaskControl,
}


class HotkeyManager:
    """Registers a global hotkey via CGEvent tap."""

    def __init__(self, modifiers: list[str], key: str, callback):
        self._modifiers = modifiers
        self._key = key
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._run_loop = None
        self._running = False

    def _compute_target_flags(self) -> int:
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
            target_keycode = KEYCODES.get(self._key.lower())

            if target_keycode is None or keycode != target_keycode:
                return event

            flags = CGEventGetFlags(event)
            target_flags = self._compute_target_flags()

            # Mask out device-dependent bits
            MODIFIER_MASK = (
                kCGEventFlagMaskCommand
                | kCGEventFlagMaskAlternate
                | kCGEventFlagMaskShift
                | kCGEventFlagMaskControl
            )
            active_mods = flags & MODIFIER_MASK

            if active_mods == target_flags:
                self._callback()
                return None  # Swallow the event
        except Exception:
            traceback.print_exc()

        return event

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            tap = CGEventTapCreate(
                kCGSessionEventTap,
                kCGHeadInsertEventTap,
                0,  # listenOnly=0 means active tap (can swallow events)
                (1 << kCGEventKeyDown),
                self._event_callback,
                None,
            )

            if tap is None:
                print(
                    "⚠️  Failed to create CGEvent tap. "
                    "Please grant Accessibility permissions in "
                    "System Settings → Privacy & Security → Accessibility."
                )
                return

            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            self._run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._run_loop, source, kCFRunLoopCommonModes)
            CFRunLoopRun()
        except Exception:
            traceback.print_exc()

    def stop(self):
        self._running = False
        if self._run_loop:
            CFRunLoopStop(self._run_loop)

    def update_hotkey(self, modifiers: list[str], key: str):
        """Update the hotkey combination. Requires restart of the tap."""
        self.stop()
        self._modifiers = modifiers
        self._key = key
        self.start()
