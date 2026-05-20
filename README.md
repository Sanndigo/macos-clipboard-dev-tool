# ✦ Liquid Glass Clipboard Manager

A glassmorphism clipboard manager for macOS — built for developers.

![macOS](https://img.shields.io/badge/macOS-12%2B-000?logo=apple)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- ** Smart Clipboard History** — Auto-detects 14+ programming languages with syntax-aware previews
- ** In-App Snippet Editor** — Edit any clip with rock-solid CodeMirror 5 (syntax highlighting, themes)
- ** Instant Activation** — `⌥V` shows/minimizes the window instantly (global hotkey via CGEvent tap)
- ** Liquid Glass UI** — Glassmorphism design with blur, transparency, and smooth animations
- ** Light & Dark Mode** — Automatically adapts to macOS system appearance
- ** Native Desktop Feel** — Standard macOS Dock integration with full Main Menu support (Cmd+C/V works!)
- ** Pin Important Clips** — Pin clips to prevent them from being evicted
- ** Keyboard-First** — Arrow keys to navigate, Enter to paste, Escape to hide

## Quick Start

### 1. Install Dependencies

```bash
cd ClipboardMacOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run in Development Mode

```bash
python main.py --debug
```

> **Note:** On first launch, macOS will ask for **Accessibility** permissions (System Settings → Privacy & Security → Accessibility). This is required for the global hotkey.

### 3. Usage

| Action | Shortcut |
|--------|----------|
| Show/Minimize | `⌥V` (Option + V) |
| Navigate clips | `↑` / `↓` |
| Copy selected | `Enter` or double-click |
| Hide window | `Escape` or click outside |
| Edit clip | Click ✏️ button |
| Pin clip | Click 📌 button |
| Search | Just start typing |

## Building the .app Bundle

```bash
# Activate venv
source .venv/bin/activate

# Build with PyInstaller
pyinstaller build.spec --noconfirm

# The app will be at:
# dist/Liquid Glass Clipboard.app
```

### Apple Silicon Optimization

The `build.spec` targets `universal2` by default (arm64 + x86_64). For a leaner Apple Silicon-only build:

```python
# In build.spec, change:
target_arch='arm64',
```

## Project Structure

```
ClipboardMacOS/
├── main.py                      # Entry point — orchestrates all services
├── app/
│   ├── api_bridge.py            # pywebview JS↔Python API bridge
│   ├── clipboard_monitor.py     # NSPasteboard polling thread
│   ├── database.py              # JSON-backed history with language detection
│   ├── hotkey_manager.py        # CGEvent tap global hotkey
│   └── settings.py              # Persistent user preferences
├── ui/
│   ├── index.html               # App shell with all panels
│   ├── css/style.css            # Liquid Glass design system
│   └── js/
│       ├── app.js               # Core UI logic
│       ├── editor.js            # CodeMirror 5 integration
│       └── settings.js          # Settings panel
├── resources/Info.plist         # macOS app metadata
├── build.spec                   # PyInstaller configuration
└── requirements.txt             # Python dependencies
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           macOS (Cocoa / WebKit)             │
├──────────────┬──────────────────────────────┤
│  Python      │  pywebview Window            │
│  Backend     │  ┌────────────────────────┐  │
│              │  │  HTML/CSS/JS Frontend  │  │
│  • Clipboard │  │  • Glassmorphism UI    │  │
│    Monitor   │  │  • CodeMirror Editor   │  │
│  • Settings  │◄─┤  • Search & Navigate   │  │
│  • Database  │─►│  • Settings Panel      │  │
│  • Hotkey    │  └────────────────────────┘  │
│    Manager   │     (JS API Bridge)          │
└──────────────┴──────────────────────────────┘
```

## Images
<img width="1512" height="982" alt="Снимок экрана — 2026-05-21 в 00 02 55" src="https://github.com/user-attachments/assets/9b7e9998-7f67-4000-9390-96f0724ece52" /><img width="1512" height="982" alt="Снимок экрана — 2026-05-21 в 00 04 00" src="https://github.com/user-attachments/assets/d6432578-b218-45d7-b626-260a7e4a2eb9" /><img width="1512" height="982" alt="Снимок экрана — 2026-05-21 в 00 16 14" src="https://github.com/user-attachments/assets/4d893aaa-f20f-4dce-b5b8-71ba8b7d36ec" />


## License

MIT
