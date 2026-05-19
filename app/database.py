"""
Clipboard history database for Liquid Glass Clipboard Manager.
Stores up to N items in a JSON file, with deduplication and language detection.

Thread-safe: all public methods are guarded by a reentrant lock.
File writes use atomic rename to prevent corruption on crash.
"""

import json
import hashlib
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from app.constants import APP_SUPPORT_DIR, DB_FILE, MAX_CLIP_TEXT_LENGTH
from app.logging_config import get_logger

logger = get_logger(__name__)

# ── Pre-compiled language detection patterns ──────────────────────

_LANG_PATTERNS: dict[str, list[re.Pattern]] = {}

_RAW_PATTERNS = {
    "python": [
        r"\bdef\s+\w+\s*\(", r"\bimport\s+\w+", r"\bclass\s+\w+.*:",
        r"\bif\s+__name__\s*==", r"print\s*\(", r"\bself\.",
    ],
    "javascript": [
        r"\bconst\s+\w+", r"\blet\s+\w+", r"\bfunction\s+\w+",
        r"=>\s*\{", r"\bconsole\.log\b", r"\bdocument\.\w+",
    ],
    "typescript": [
        r":\s*(string|number|boolean|any)\b", r"\binterface\s+\w+",
        r"\btype\s+\w+\s*=", r"<\w+>",
    ],
    "html": [
        r"<(!DOCTYPE|html|head|body|div|span|p|a|img)\b", r"</\w+>",
    ],
    "css": [
        r"\{[^}]*:\s*[^;]+;", r"\.[\w-]+\s*\{", r"@media\s+",
        r"#[\w-]+\s*\{",
    ],
    "json": [
        r'^\s*\{', r'"\w+":\s*',
    ],
    "sql": [
        r"\bSELECT\b.*\bFROM\b", r"\bINSERT\s+INTO\b",
        r"\bCREATE\s+TABLE\b", r"\bWHERE\b",
    ],
    "bash": [
        r"#!/bin/(ba)?sh", r"\becho\s+", r"\bexport\s+\w+=",
        r"\|\s*grep\b", r"\bsudo\s+",
    ],
    "swift": [
        r"\bfunc\s+\w+\s*\(", r"\bvar\s+\w+\s*:", r"\blet\s+\w+\s*:",
        r"\bimport\s+Foundation\b", r"\bstruct\s+\w+",
    ],
    "rust": [
        r"\bfn\s+\w+\s*\(", r"\blet\s+mut\s+", r"\bimpl\s+\w+",
        r"\buse\s+std::", r"println!\(",
    ],
    "go": [
        r"\bfunc\s+\w+\s*\(", r"\bpackage\s+\w+", r"\bfmt\.Println\b",
        r":=\s*", r"\bimport\s+\(",
    ],
    "cpp": [
        r"#include\s*<", r"\bstd::\w+", r"\bint\s+main\s*\(",
        r"\bcout\s*<<", r"\bnamespace\s+",
    ],
    "java": [
        r"\bpublic\s+class\s+", r"\bpublic\s+static\s+void\s+main\b",
        r"\bSystem\.out\.print", r"\bimport\s+java\.",
    ],
    "ruby": [
        r"\bdef\s+\w+", r"\bputs\s+", r"\bend\b",
        r"\brequire\s+['\"]", r"\battr_accessor\b",
    ],
}

# Pre-compile all patterns at import time for performance
for _lang, _patterns in _RAW_PATTERNS.items():
    _flags = re.IGNORECASE if _lang == "sql" else 0
    _LANG_PATTERNS[_lang] = [re.compile(p, _flags) for p in _patterns]


def detect_language(text: str) -> str:
    """Detect the likely programming language of a text snippet."""
    if not text or len(text.strip()) < 5:
        return "plaintext"

    scores: dict[str, int] = {}
    for lang, compiled_patterns in _LANG_PATTERNS.items():
        score = 0
        for pattern in compiled_patterns:
            matches = pattern.findall(text)
            score += len(matches)
        if score > 0:
            scores[lang] = score

    if not scores:
        return "plaintext"

    return max(scores, key=scores.get)


def _hash(text: str) -> str:
    """Generate a truncated SHA-256 hash for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class ClipboardDatabase:
    """JSON-backed clipboard history with dedup, language detection, and thread safety.

    All public methods acquire a reentrant lock before accessing or modifying
    the internal items list. File writes use atomic rename to prevent corruption.
    """

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._items: list[dict] = []
        self._lock = threading.RLock()
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load items from disk. Called only during __init__ (no lock needed)."""
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._items = data
                else:
                    logger.warning("Database file contained non-list data; resetting.")
                    self._items = []
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.error("Failed to load database: %s", e)
                self._items = []

    def _save(self):
        """Atomically write items to disk. Must be called with self._lock held."""
        try:
            # Write to a temp file first, then atomically rename
            fd, tmp_path = tempfile.mkstemp(
                dir=str(APP_SUPPORT_DIR), suffix=".tmp", prefix="history_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._items, f, indent=2, ensure_ascii=False)

                # Atomic rename (POSIX guarantees this)
                os.replace(tmp_path, str(DB_FILE))

                # Set restrictive permissions (owner-only)
                os.chmod(str(DB_FILE), 0o600)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error("Failed to save database: %s", e)

    def add(self, text: str, auto_trim: bool = False) -> Optional[dict]:
        """Add a clipboard entry. Returns the item dict or None if skipped.

        Deduplication: if the text already exists, it is moved to the top
        while preserving its pinned status.
        """
        if not text or not text.strip():
            return None

        if auto_trim:
            text = text.strip()

        # Enforce maximum text length to prevent memory exhaustion
        if len(text) > MAX_CLIP_TEXT_LENGTH:
            text = text[:MAX_CLIP_TEXT_LENGTH]

        text_hash = _hash(text)

        with self._lock:
            # Check for existing duplicate — preserve pinned status
            existing_pinned = False
            for existing in self._items:
                if existing.get("hash") == text_hash:
                    existing_pinned = existing.get("pinned", False)
                    break

            # Remove the old duplicate (will be re-added at top)
            self._items = [item for item in self._items if item.get("hash") != text_hash]

            language = detect_language(text)
            item = {
                "id": text_hash,
                "hash": text_hash,
                "text": text,
                "language": language,
                "timestamp": time.time(),
                "pinned": existing_pinned,
            }

            self._items.insert(0, item)

            # Enforce max size (keep pinned items safe)
            self._enforce_max_items()

            self._save()
            return item

    def _enforce_max_items(self):
        """Trim unpinned items to stay within max_items. Must be called with lock held."""
        if len(self._items) <= self.max_items:
            return

        pinned = [i for i in self._items if i.get("pinned")]
        unpinned = [i for i in self._items if not i.get("pinned")]

        excess = len(self._items) - self.max_items
        # Only trim unpinned items
        if excess > 0 and len(unpinned) > 0:
            items_to_remove = min(excess, len(unpinned))
            unpinned = unpinned[:-items_to_remove]

        self._items = pinned + unpinned
        self._items.sort(key=lambda x: x["timestamp"], reverse=True)

    def get_all(self) -> list[dict]:
        """Return a shallow copy of all items, newest first."""
        with self._lock:
            return [dict(item) for item in self._items]

    def get_by_id(self, item_id: str) -> Optional[dict]:
        """Return a copy of the item with the given ID, or None."""
        if not isinstance(item_id, str) or len(item_id) > 64:
            return None
        with self._lock:
            for item in self._items:
                if item["id"] == item_id:
                    return dict(item)
            return None

    def update_text(self, item_id: str, new_text: str) -> Optional[dict]:
        """Update the text of an existing item (from editor).

        Returns the updated item dict with new ID, or None if not found.
        The caller should use the returned item's new ID for subsequent operations.
        """
        if not isinstance(item_id, str) or len(item_id) > 64:
            return None
        if not isinstance(new_text, str) or not new_text.strip():
            return None
        if len(new_text) > MAX_CLIP_TEXT_LENGTH:
            new_text = new_text[:MAX_CLIP_TEXT_LENGTH]

        with self._lock:
            for item in self._items:
                if item["id"] == item_id:
                    new_hash = _hash(new_text)

                    # Check if the new text collides with another existing item
                    for other in self._items:
                        if other["id"] != item_id and other.get("hash") == new_hash:
                            # Remove the other item (the edited one takes precedence)
                            self._items.remove(other)
                            break

                    item["text"] = new_text
                    item["language"] = detect_language(new_text)
                    item["hash"] = new_hash
                    item["id"] = new_hash
                    self._save()
                    return dict(item)
            return None

    def delete(self, item_id: str) -> bool:
        """Delete an item by ID. Returns True if an item was removed."""
        if not isinstance(item_id, str) or len(item_id) > 64:
            return False
        with self._lock:
            before = len(self._items)
            self._items = [i for i in self._items if i["id"] != item_id]
            if len(self._items) < before:
                self._save()
                return True
            return False

    def toggle_pin(self, item_id: str) -> Optional[dict]:
        """Toggle pin status for an item. Returns the updated item or None."""
        if not isinstance(item_id, str) or len(item_id) > 64:
            return None
        with self._lock:
            for item in self._items:
                if item["id"] == item_id:
                    item["pinned"] = not item.get("pinned", False)
                    self._save()
                    return dict(item)
            return None

    def clear(self):
        """Remove all items from history."""
        with self._lock:
            self._items = []
            self._save()

    def set_max(self, max_items: int):
        """Update the maximum number of items and enforce the new limit."""
        with self._lock:
            self.max_items = max(10, min(max_items, 500))
            self._enforce_max_items()
            self._save()
