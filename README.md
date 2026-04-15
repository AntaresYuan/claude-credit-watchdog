# 🐶 Claude Credit Watchdog

A macOS menu bar app that monitors your Claude Code credit resets, fires hard-to-miss alerts, and automatically resumes your sessions — so you never lose momentum when the 5-hour limit hits.

**[claude-credit-watchdog.netlify.app](https://claude-credit-watchdog.netlify.app)**

![macOS 13+](https://img.shields.io/badge/macOS-13%2B-blue?style=flat-square)
![License MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Built with Tauri](https://img.shields.io/badge/built%20with-Tauri-orange?style=flat-square)

---

## What It Does

- **Detects credit exhaustion** via Claude Code `StopFailure` hooks + Terminal.app content scanning fallback
- **Shows a countdown** in a floating menu bar widget (hides from Dock)
- **Fires alerts** when credits reset: macOS notification + blocking dialog + voice announcement
- **Auto-resumes** by injecting `"Please continue with what we left"` into the correct Terminal.app tab
- **100% local** — no accounts, no cloud, no telemetry

## Install

### Option A — DMG (recommended)

1. Download the latest DMG from [Releases](https://github.com/AntaresYuan/claude-credit-watchdog/releases)
2. Open the DMG, drag the app to `~/Applications`
3. Right-click → **Open** the first time (required for unsigned apps)
4. Run the installer to set up the daemon and Claude Code hooks:

```sh
bash ~/Applications/Claude\ Credit\ Watchdog.app/Contents/Resources/scripts/install.sh
```

5. Restart Claude Code — you're done.

### Option B — Build from source

Requirements: [Rust](https://rustup.rs), [Node.js 18+](https://nodejs.org), macOS 13+

```sh
git clone https://github.com/AntaresYuan/claude-credit-watchdog.git
cd claude-credit-watchdog
npm install
npm run tauri:build
```

The built app lands in `src-tauri/target/release/bundle/macos/`.

## Requirements

- macOS 13 Ventura or later
- [Claude Code](https://claude.ai/code) CLI installed
- Terminal.app (for AppleScript tab injection)
- Python 3 (pre-installed on macOS)

## How It Works

```
Claude Code session hits rate limit
        │
        ▼
StopFailure hook fires → ccwatch.py records session + resets_at timestamp
        │
        ▼
Background daemon polls every 15s
        │
        ├─ Widget pill: "Credit locked · Resets in Xm"
        │
        └─ When resets_at arrives:
               ├─ macOS notification
               ├─ Blocking dialog
               ├─ Voice announcement ("say")
               └─ AppleScript injects "Please continue with what we left"
                  into the matching Terminal.app tab
```

## Project Layout

```
├── src/                  React UI (menu bar widget + settings)
├── src-tauri/            Tauri/Rust shell
├── scripts/
│   ├── ccwatch.py        Core Python daemon
│   ├── ccwatch           CLI wrapper
│   └── install.sh        One-shot installer
├── assets/
│   ├── claude-plugin/    Hooks + statusline script
│   └── launchd/          LaunchAgent plist template
└── docs/                 Landing page (GitHub Pages)
```

## Uninstall

```sh
launchctl unload ~/Library/LaunchAgents/com.antaresyuan.credit-watchdog.plist
rm ~/Library/LaunchAgents/com.antaresyuan.credit-watchdog.plist
rm -rf ~/.local/share/credit-watchdog
rm ~/.local/bin/ccwatch
rm -rf ~/.claude/plugins/credit-watchdog
rm -rf ~/Applications/Claude\ Credit\ Watchdog.app
```

## Contributing

PRs welcome. Open an issue first for anything non-trivial.

## License

MIT
