"""
Clipboard monitoring thread for Liquid Glass Clipboard Manager.
Uses PyObjC's NSPasteboard to poll the system clipboard for changes.
"""

import threading
import time
import traceback

from AppKit import NSPasteboard, NSStringPboardType


class ClipboardMonitor:
    """Monitors the macOS system clipboard for new text content."""

    def __init__(self, on_new_clip=None, poll_interval: float = 0.5):
        self._on_new_clip = on_new_clip
        self._poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_change_count = 0

    def start(self):
        if self._running:
            return
        self._running = True
        # Initialize with current change count so we don't capture stale data
        pb = NSPasteboard.generalPasteboard()
        self._last_change_count = pb.changeCount()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                pb = NSPasteboard.generalPasteboard()
                current_count = pb.changeCount()

                if current_count != self._last_change_count:
                    self._last_change_count = current_count
                    text = pb.stringForType_(NSStringPboardType)
                    if text and self._on_new_clip:
                        self._on_new_clip(str(text))
            except Exception:
                traceback.print_exc()

            time.sleep(self._poll_interval)

    @staticmethod
    def set_clipboard(text: str):
        """Write text to the system clipboard."""
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSStringPboardType)

    @staticmethod
    def get_clipboard() -> str | None:
        """Read current text from the system clipboard."""
        pb = NSPasteboard.generalPasteboard()
        return pb.stringForType_(NSStringPboardType)
