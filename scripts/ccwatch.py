#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


APP = "credit-watchdog"
HOME = Path.home()
INSTALL_DIR = Path(os.environ.get("CCWATCH_INSTALL_DIR", HOME / ".local" / "share" / APP))
CONFIG_DIR = Path(os.environ.get("CCWATCH_CONFIG_DIR", HOME / ".config" / APP))
STATE_DIR = Path(os.environ.get("CCWATCH_STATE_DIR", HOME / ".local" / "state" / APP))
SESSION_DIR = STATE_DIR / "sessions"
LOG_DIR = STATE_DIR / "logs"
LOG_PATH = LOG_DIR / "watcher.log"
SETTINGS_PATH = CONFIG_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "poll_interval_seconds": 15,
    "auto_resume": True,
    "alert_mode": "dialog-sound-notification",
    "sound_enabled": True,
    "dialog_enabled": True,
    "notification_enabled": True,
    "max_retry_count": 3,
    "watcher_enabled": True,
}

RATE_LIMIT_TEXT = re.compile(
    r"(session limit|rate limit|used 100% of your session limit|no credit|credit.*renew|quota|(?:hit|reached)\s+your\s+limit|usage limit)",
    re.IGNORECASE,
)
RESETS_AT_TEXT = re.compile(
    r"resets?(?:\s+at)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
    re.IGNORECASE,
)


def ensure_dirs() -> None:
    for path in (INSTALL_DIR, CONFIG_DIR, STATE_DIR, SESSION_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None = None) -> str:
    value = value or now_utc()
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def log(message: str) -> None:
    ensure_dirs()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{isoformat()}] {message}\n")


def get_settings() -> dict[str, Any]:
    settings = DEFAULT_SETTINGS | read_json(SETTINGS_PATH, {})
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = DEFAULT_SETTINGS | settings
    write_json(SETTINGS_PATH, merged)
    return merged


def session_path(session_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", session_id).strip("-") or "unknown-session"
    return SESSION_DIR / f"{safe_id}.json"


def list_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for path in sorted(SESSION_DIR.glob("*.json")):
        payload = read_json(path, None)
        if isinstance(payload, dict):
            sessions.append(payload)
    return sorted(sessions, key=lambda item: item.get("last_seen_at", ""), reverse=True)


def load_session(session_id: str) -> dict[str, Any] | None:
    payload = read_json(session_path(session_id), None)
    return payload if isinstance(payload, dict) else None


def save_session(session: dict[str, Any]) -> dict[str, Any]:
    session.setdefault("resume_attempts", 0)
    session.setdefault("status", "active")
    write_json(session_path(session["session_id"]), session)
    return session


def delete_session(session_id: str) -> None:
    path = session_path(session_id)
    if path.exists():
        path.unlink()


def stdin_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {"raw": raw}


def tty_name() -> str:
    result = subprocess.run(["tty"], capture_output=True, text=True, check=False)
    value = result.stdout.strip()
    return "" if value == "not a tty" else value


def session_id_from_tty(tty: str) -> str:
    suffix = tty.replace("/dev/", "").replace("/", "-").replace(".", "-").strip("-")
    return f"tty-{suffix or 'unknown'}"


def find_session_by_tty(tty: str) -> dict[str, Any] | None:
    if not tty:
        return None
    for session in list_sessions():
        if session.get("tty") == tty:
            return session
    return None


def current_session(payload: dict[str, Any]) -> dict[str, Any]:
    tty = tty_name()
    session = None
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        session = load_session(session_id)
    if session is None and tty:
        session = find_session_by_tty(tty)
    if session is None:
        session = {
            "session_id": session_id or session_id_from_tty(tty),
            "started_at": isoformat(),
            "resume_attempts": 0,
        }
    session["tty"] = tty or session.get("tty", "")
    session["cwd"] = payload.get("cwd") or session.get("cwd") or os.getcwd()
    session["last_seen_at"] = isoformat()
    return session


def flatten(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def is_rate_limited_text(text: str) -> bool:
    return bool(text and RATE_LIMIT_TEXT.search(text))


def recent_terminal_text(text: str, max_chars: int = 1200) -> str:
    if not text:
        return ""
    collapsed = " ".join(text.split())
    return collapsed[-max_chars:]


def is_recent_rate_limited_text(text: str) -> bool:
    return is_rate_limited_text(recent_terminal_text(text))


def parse_reset_time(text: str) -> str | None:
    match = RESETS_AT_TEXT.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    local_now = datetime.now().astimezone()
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_statusline(session: dict[str, Any]) -> str:
    used = session.get("used_percentage")
    reset_at = parse_iso(session.get("resets_at"))
    status = session.get("status", "active")
    if used is not None and reset_at:
        delta = reset_at - now_utc()
        minutes = max(int(delta.total_seconds() // 60), 0)
        return f"CW {used:.0f}% · {minutes}m"
    if status == "rate_limited" and reset_at:
        delta = reset_at - now_utc()
        minutes = max(int(delta.total_seconds() // 60), 0)
        return f"CW hold · {minutes}m"
    return "CW ready"


def terminal_snapshot() -> list[dict[str, Any]]:
    def sanitize_text(value: str) -> str:
        return (
            value.replace("\r", " ")
            .replace("\n", " ")
            .replace("\t", " ")
            .replace(chr(31), " ")
            .replace(chr(30), " ")
        )

    def run_osascript(command: str, *, required: bool = False) -> str:
        result = subprocess.run(["osascript", "-e", command], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout.rstrip("\n")
        message = result.stderr.strip()
        if required:
            raise RuntimeError(message or f"osascript failed: {command}")
        return ""

    try:
        window_count = int(run_osascript('tell application "Terminal" to count of windows', required=True) or "0")
    except (RuntimeError, ValueError) as issue:
        log(f"terminal snapshot failed: {issue}")
        return []

    tabs: list[dict[str, Any]] = []
    try:
        for window_index in range(1, window_count + 1):
            window_id = run_osascript(
                f'tell application "Terminal" to id of window {window_index}',
                required=True,
            )
            tab_count = int(
                run_osascript(
                    f'tell application "Terminal" to count of tabs of window {window_index}',
                    required=True,
                )
                or "0"
            )
            for tab_index in range(1, tab_count + 1):
                tty = run_osascript(f'tell application "Terminal" to tty of tab {tab_index} of window {window_index}')
                busy = run_osascript(f'tell application "Terminal" to busy of tab {tab_index} of window {window_index}')
                processes = run_osascript(
                    f'tell application "Terminal" to processes of tab {tab_index} of window {window_index}'
                )
                custom_title = run_osascript(
                    f'tell application "Terminal" to custom title of tab {tab_index} of window {window_index}'
                )
                contents = run_osascript(
                    f'tell application "Terminal" to contents of tab {tab_index} of window {window_index}'
                )
                tabs.append(
                    {
                        "window_id": window_id,
                        "tab_index": str(tab_index),
                        "tty": sanitize_text(tty),
                        "busy": busy.strip().lower() == "true",
                        "processes": [segment.strip() for segment in processes.split(",") if segment.strip()],
                        "custom_title": sanitize_text(custom_title),
                        "contents": sanitize_text(contents),
                    }
                )
    except (RuntimeError, ValueError) as issue:
        log(f"terminal snapshot failed: {issue}")
        return []
    return tabs


def update_session_from_tab(session: dict[str, Any], tab: dict[str, Any]) -> dict[str, Any]:
    contents = tab.get("contents", "")
    recent_contents = recent_terminal_text(contents)
    if not session.get("tty") and tab.get("tty"):
        session["tty"] = tab["tty"]
    if not contents:
        return session
    if not is_recent_rate_limited_text(contents):
        if session.get("status") == "rate_limited":
            session["status"] = "active"
            session.pop("resets_at", None)
            session.pop("error_summary", None)
            session.pop("dismissed_for_reset", None)
            session["detection_source"] = "terminal_text"
            session["last_seen_at"] = isoformat()
        return session
    reset_guess = parse_reset_time(recent_contents)
    session["status"] = "rate_limited"
    session["error_summary"] = "Terminal text indicates a credit/session limit"
    session["detection_source"] = "terminal_text"
    if reset_guess:
        existing_reset = parse_iso(session.get("resets_at"))
        # Don't overwrite a past-due resets_at — terminal still shows stale text;
        # bumping to "next day" would hide the already-due alert.
        if existing_reset is None or existing_reset > now_utc():
            if reset_guess != session.get("resets_at"):
                session.pop("dismissed_for_reset", None)
            session["resets_at"] = reset_guess
    session["last_seen_at"] = isoformat()
    return session


def matching_tabs(session: dict[str, Any], tabs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tty = session.get("tty")
    if tty:
        exact = [tab for tab in tabs if tab.get("tty") == tty]
        if exact:
            return exact
    priority = []
    fallback = []
    for tab in tabs:
        processes = ",".join(tab.get("processes", []))
        contents = tab.get("contents", "")
        if is_recent_rate_limited_text(contents):
            priority.append(tab)
            continue
        if "claude code" in contents.lower():
            fallback.append(tab)
            continue
        if "claude" in processes.lower():
            fallback.append(tab)
    return priority + fallback


def inject_resume(tab: dict[str, Any]) -> bool:
    script = r'''
on run argv
  set targetWindowId to item 1 of argv
  set targetTabIndex to item 2 of argv
  set commandText to item 3 of argv

  tell application "Terminal"
    set targetWindow to first window whose id is (targetWindowId as integer)
    do script commandText in tab (targetTabIndex as integer) of targetWindow
  end tell
end run
'''
    result = subprocess.run(
        ["osascript", "-e", script, tab["window_id"], tab["tab_index"], "Please continue with what we left"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def notify(title: str, body: str, settings: dict[str, Any]) -> None:
    if settings.get("notification_enabled", True):
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            capture_output=True,
            text=True,
            check=False,
        )
    if settings.get("dialog_enabled", True):
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display dialog "{body}" with title "{title}" buttons {{"OK"}} default button "OK" giving up after 15',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if settings.get("sound_enabled", True):
        subprocess.run(["say", title], capture_output=True, text=True, check=False)


def command_session_start(_: argparse.Namespace) -> int:
    payload = stdin_payload()
    session = current_session(payload)
    session["status"] = "active"
    session["detection_source"] = session.get("detection_source") or "hook"
    session["last_seen_at"] = isoformat()
    save_session(session)
    print(json.dumps(session))
    return 0


def command_stop_failure(_: argparse.Namespace) -> int:
    payload = stdin_payload()
    haystack = flatten(payload)
    session = current_session(payload)
    if is_rate_limited_text(haystack):
        previous_reset = session.get("resets_at")
        reset_guess = parse_reset_time(haystack)
        session["status"] = "rate_limited"
        session["error_summary"] = haystack[:240]
        session["detection_source"] = "hook"
        if reset_guess:
            session["resets_at"] = reset_guess
        if previous_reset != session.get("resets_at"):
            session.pop("dismissed_for_reset", None)
        save_session(session)
    print(json.dumps(session))
    return 0


def command_statusline(_: argparse.Namespace) -> int:
    payload = stdin_payload()
    session = current_session(payload)
    primary = (((payload.get("rate_limits") or {}).get("primary")) or {})
    used = primary.get("used_percentage", primary.get("used_percent"))
    resets_at = primary.get("resets_at")
    if used is not None:
        session["used_percentage"] = float(used)
    if resets_at:
        session["resets_at"] = datetime.fromtimestamp(int(resets_at), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        session["detection_source"] = "statusline"
    if session.get("used_percentage", 0) >= 100 and session.get("resets_at"):
        session["status"] = "rate_limited"
    elif session.get("status") != "resumed":
        session["status"] = session.get("status", "active")
    save_session(session)
    print(render_statusline(session))
    return 0


def do_resume(session_id: str) -> dict[str, Any]:
    session = load_session(session_id)
    if session is None:
        return {"ok": False, "error": "session not found", "session_id": session_id}
    tabs = terminal_snapshot()
    targets = matching_tabs(session, tabs)
    if not targets:
        session["status"] = "stale"
        save_session(session)
        return {"ok": False, "error": "no matching Terminal tab found", "session_id": session_id}
    sent = 0
    for tab in targets:
        if inject_resume(tab):
            sent += 1
    session["last_resume_at"] = isoformat()
    session["resume_attempts"] = int(session.get("resume_attempts", 0)) + 1
    session["status"] = "resumed" if sent else "rate_limited"
    save_session(session)
    return {"ok": sent > 0, "sent": sent, "session": session}


def command_resume_session(args: argparse.Namespace) -> int:
    print(json.dumps(do_resume(args.session_id)))
    return 0


def command_resume_due(_: argparse.Namespace) -> int:
    results = []
    current = now_utc()
    for session in list_sessions():
        reset_at = parse_iso(session.get("resets_at"))
        if session.get("status") != "rate_limited" or reset_at is None or reset_at > current:
            continue
        results.append(do_resume(session["session_id"]))
    print(json.dumps(results))
    return 0


def command_dismiss_alert(args: argparse.Namespace) -> int:
    session = load_session(args.session_id)
    if session is None:
        print(json.dumps({"ok": False, "error": "session not found"}))
        return 1
    session["dismissed_for_reset"] = session.get("resets_at")
    save_session(session)
    print(json.dumps({"ok": True, "session": session}))
    return 0


def command_get_sessions(_: argparse.Namespace) -> int:
    print(json.dumps(list_sessions()))
    return 0


def command_get_settings(_: argparse.Namespace) -> int:
    print(json.dumps(get_settings()))
    return 0


def command_save_settings(args: argparse.Namespace) -> int:
    payload = json.loads(args.payload)
    print(json.dumps(save_settings(payload)))
    return 0


def command_toggle_watcher(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings["watcher_enabled"] = args.enabled.lower() == "true"
    print(json.dumps(save_settings(settings)))
    return 0


def command_status(_: argparse.Namespace) -> int:
    settings = get_settings()
    sessions = list_sessions()
    current = now_utc()
    due = 0
    waiting = 0
    next_reset = None
    for session in sessions:
        reset_at = parse_iso(session.get("resets_at"))
        if session.get("status") == "rate_limited":
            waiting += 1
            if reset_at and reset_at <= current:
                due += 1
        if reset_at and (next_reset is None or reset_at < next_reset):
            next_reset = reset_at
    print(
        json.dumps(
            {
                "watcher_enabled": settings.get("watcher_enabled", True),
                "auto_resume": settings.get("auto_resume", True),
                "session_count": len(sessions),
                "waiting_count": waiting,
                "due_count": due,
                "next_reset_at": isoformat(next_reset) if next_reset else None,
                "log_dir": str(LOG_DIR),
                "state_dir": str(STATE_DIR),
            }
        )
    )
    return 0


def command_open_log_dir(_: argparse.Namespace) -> int:
    ensure_dirs()
    subprocess.run(["open", str(LOG_DIR)], check=False)
    print(json.dumps({"ok": True, "path": str(LOG_DIR)}))
    return 0


def watcher_tick() -> dict[str, Any]:
    settings = get_settings()
    tabs = terminal_snapshot()
    current = now_utc()
    sessions = list_sessions()

    # Collect due sessions BEFORE terminal update — otherwise update_session_from_tab
    # may call parse_reset_time() on stale terminal text and bump resets_at to next day,
    # causing the alert to never fire and the countdown to restart at ~24h.
    due_sessions: list[dict[str, Any]] = []
    for session in sessions:
        reset_at = parse_iso(session.get("resets_at"))
        if session.get("status") == "rate_limited" and reset_at and reset_at <= current:
            if session.get("dismissed_for_reset") == session.get("resets_at"):
                continue
            due_sessions.append(session)

    updated_sessions = {session["session_id"]: session for session in sessions}
    for session in sessions:
        for tab in matching_tabs(session, tabs):
            update_session_from_tab(session, tab)
            save_session(session)
            updated_sessions[session["session_id"]] = session
            break

    resume_results = []
    if settings.get("watcher_enabled", True) and due_sessions:
        if settings.get("auto_resume", True):
            for session in due_sessions:
                result = do_resume(session["session_id"])
                resume_results.append(result)
        notify(
            "Claude credits should be back",
            f"{len(due_sessions)} session(s) reached their reset time.",
            settings,
        )

    summary = {
        "due_count": len(due_sessions),
        "tabs_seen": len(tabs),
        "resume_results": resume_results,
        "watcher_enabled": settings.get("watcher_enabled", True),
    }
    log(f"watcher tick: {json.dumps(summary, ensure_ascii=False)}")
    return summary


def command_watcher_once(_: argparse.Namespace) -> int:
    print(json.dumps(watcher_tick()))
    return 0


def command_watcher_daemon(_: argparse.Namespace) -> int:
    ensure_dirs()
    log("watcher daemon started")
    while True:
        settings = get_settings()
        if settings.get("watcher_enabled", True):
            watcher_tick()
        time.sleep(max(int(settings.get("poll_interval_seconds", 15)), 5))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccwatch")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("session-start", command_session_start),
        ("stop-failure", command_stop_failure),
        ("statusline", command_statusline),
        ("resume-due", command_resume_due),
        ("get-sessions", command_get_sessions),
        ("get-settings", command_get_settings),
        ("status", command_status),
        ("open-log-dir", command_open_log_dir),
        ("watcher-once", command_watcher_once),
        ("watcher-daemon", command_watcher_daemon),
    ):
        command = sub.add_parser(name)
        command.set_defaults(func=handler)

    resume = sub.add_parser("resume-session")
    resume.add_argument("session_id")
    resume.set_defaults(func=command_resume_session)

    dismiss = sub.add_parser("dismiss-alert")
    dismiss.add_argument("session_id")
    dismiss.set_defaults(func=command_dismiss_alert)

    save = sub.add_parser("save-settings")
    save.add_argument("payload")
    save.set_defaults(func=command_save_settings)

    toggle = sub.add_parser("toggle-watcher")
    toggle.add_argument("enabled")
    toggle.set_defaults(func=command_toggle_watcher)

    return parser


def main() -> int:
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
