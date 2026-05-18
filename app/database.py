"""
Clipboard history database for Liquid Glass Clipboard Manager.
Stores up to N items in a JSON file, with deduplication and language detection.
"""

import json
import hashlib
import re
import time
from pathlib import Path
from typing import Optional


APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "LiquidGlassClipboard"
DB_FILE = APP_SUPPORT_DIR / "history.json"

# Heuristic language detection patterns
LANG_PATTERNS = {
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
        r"\{[^}]*:\s*[^;]+;", r"\.([\w-]+)\s*\{", r"@media\s+",
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


def detect_language(text: str) -> str:
    """Detect the likely programming language of a text snippet."""
    if not text or len(text.strip()) < 5:
        return "plaintext"

    scores = {}
    for lang, patterns in LANG_PATTERNS.items():
        score = 0
        for pattern in patterns:
            flags = re.IGNORECASE if lang == "sql" else 0
            matches = re.findall(pattern, text, flags)
            score += len(matches)
        if score > 0:
            scores[lang] = score

    if not scores:
        return "plaintext"

    # Return the language with the highest score
    return max(scores, key=scores.get)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class ClipboardDatabase:
    """JSON-backed clipboard history with dedup and language detection."""

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._items: list[dict] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r") as f:
                    self._items = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._items = []

    def _save(self):
        with open(DB_FILE, "w") as f:
            json.dump(self._items, f, indent=2, ensure_ascii=False)

    def add(self, text: str, auto_trim: bool = False) -> Optional[dict]:
        """Add a clipboard entry. Returns the item dict or None if duplicate."""
        if not text or not text.strip():
            return None

        if auto_trim:
            text = text.strip()

        text_hash = _hash(text)

        # Remove existing duplicate (will be re-added at top)
        self._items = [item for item in self._items if item.get("hash") != text_hash]

        language = detect_language(text)
        item = {
            "id": text_hash,
            "hash": text_hash,
            "text": text,
            "language": language,
            "timestamp": time.time(),
            "pinned": False,
        }

        self._items.insert(0, item)

        # Enforce max size (keep pinned items safe)
        if len(self._items) > self.max_items:
            unpinned = [i for i in self._items if not i.get("pinned")]
            pinned = [i for i in self._items if i.get("pinned")]
            excess = len(self._items) - self.max_items
            if len(unpinned) > excess:
                unpinned = unpinned[:-excess]
            self._items = pinned + unpinned
            self._items.sort(key=lambda x: x["timestamp"], reverse=True)

        self._save()
        return item

    def get_all(self) -> list[dict]:
        """Return all items, newest first."""
        return list(self._items)

    def get_by_id(self, item_id: str) -> Optional[dict]:
        for item in self._items:
            if item["id"] == item_id:
                return item
        return None

    def update_text(self, item_id: str, new_text: str) -> Optional[dict]:
        """Update the text of an existing item (from editor)."""
        for item in self._items:
            if item["id"] == item_id:
                item["text"] = new_text
                item["language"] = detect_language(new_text)
                item["hash"] = _hash(new_text)
                item["id"] = item["hash"]
                self._save()
                return item
        return None

    def delete(self, item_id: str) -> bool:
        before = len(self._items)
        self._items = [i for i in self._items if i["id"] != item_id]
        if len(self._items) < before:
            self._save()
            return True
        return False

    def toggle_pin(self, item_id: str) -> Optional[dict]:
        for item in self._items:
            if item["id"] == item_id:
                item["pinned"] = not item.get("pinned", False)
                self._save()
                return item
        return None

    def clear(self):
        self._items = []
        self._save()

    def set_max(self, max_items: int):
        self.max_items = max_items
