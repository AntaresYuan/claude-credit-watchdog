#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
APP_NAME="Claude Credit Watchdog"
APP_SLUG="credit-watchdog"
INSTALL_DIR="$HOME/.local/share/$APP_SLUG"
BIN_DIR="$HOME/.local/bin"
CLAUDE_PLUGIN_DIR="$HOME/.claude/plugins/$APP_SLUG"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CONFIG_DIR="$HOME/.config/$APP_SLUG"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LAUNCH_AGENT_FILE="$LAUNCH_AGENTS_DIR/com.antaresyuan.credit-watchdog.plist"
APPLICATIONS_DIR="$HOME/Applications"
APP_BUNDLE_NAME="Claude Credit Watchdog.app"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$CLAUDE_PLUGIN_DIR" "$CONFIG_DIR" "$LAUNCH_AGENTS_DIR" "$APPLICATIONS_DIR"

cp "$ROOT_DIR/scripts/ccwatch.py" "$INSTALL_DIR/ccwatch.py"
cp "$ROOT_DIR/scripts/ccwatch" "$BIN_DIR/ccwatch"
chmod +x "$INSTALL_DIR/ccwatch.py" "$BIN_DIR/ccwatch"

rm -rf "$CLAUDE_PLUGIN_DIR"
mkdir -p "$CLAUDE_PLUGIN_DIR"
cp -R "$ROOT_DIR/assets/claude-plugin/." "$CLAUDE_PLUGIN_DIR/"
find "$CLAUDE_PLUGIN_DIR" -type f -name "*.sh" -exec chmod +x {} \;

sed \
  -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
  "$ROOT_DIR/assets/launchd/com.antaresyuan.credit-watchdog.plist" > "$LAUNCH_AGENT_FILE"

python3 - "$CLAUDE_SETTINGS" "$CLAUDE_PLUGIN_DIR" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1]).expanduser()
plugin_dir = Path(sys.argv[2]).expanduser()
if settings_path.exists():
    data = json.loads(settings_path.read_text())
else:
    data = {}

data["statusLine"] = {
    "type": "command",
    "command": f"bash {plugin_dir / 'scripts' / 'statusline.sh'}",
    "refreshInterval": 5
}

settings_path.parent.mkdir(parents=True, exist_ok=True)
settings_path.write_text(json.dumps(data, indent=2) + "\n")
PY

launchctl unload "$LAUNCH_AGENT_FILE" >/dev/null 2>&1 || true
launchctl load "$LAUNCH_AGENT_FILE"

if command -v cargo >/dev/null 2>&1; then
  (
    cd "$ROOT_DIR"
    if [ ! -d node_modules ]; then
      npm install
    fi
    npm run tauri:build
  )

  BUILT_APP="$ROOT_DIR/src-tauri/target/release/bundle/macos/$APP_BUNDLE_NAME"
  if [ -d "$BUILT_APP" ]; then
    rm -rf "$APPLICATIONS_DIR/$APP_BUNDLE_NAME"
    cp -R "$BUILT_APP" "$APPLICATIONS_DIR/$APP_BUNDLE_NAME"
  fi
fi

cat <<EOF
Installed:
  app support: $INSTALL_DIR
  CLI wrapper: $BIN_DIR/ccwatch
  Claude plugin: $CLAUDE_PLUGIN_DIR
  launch agent: $LAUNCH_AGENT_FILE
  app bundle target: $APPLICATIONS_DIR/$APP_BUNDLE_NAME

Next:
  1. Add $BIN_DIR to PATH if needed.
  2. If Rust was missing, install it and rerun this script to build the menu bar app.
EOF
