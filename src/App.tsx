import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { LogicalSize } from "@tauri-apps/api/dpi";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { api } from "./lib/api";
import type { Overview, SessionRecord, WatchdogSettings } from "./lib/types";

const CURRENT_VERSION = "0.1.0";
const RELEASES_URL = "https://github.com/AntaresYuan/claude-credit-watchdog/releases/latest";
const RELEASES_API = "https://api.github.com/repos/AntaresYuan/claude-credit-watchdog/releases/latest";

function useUpdateCheck() {
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const checked = useRef(false);

  useEffect(() => {
    if (checked.current) return;
    checked.current = true;
    fetch(RELEASES_API)
      .then((r) => r.json())
      .then((data) => {
        const latest = (data.tag_name as string | undefined)?.replace(/^v/, "");
        if (latest && latest !== CURRENT_VERSION) setLatestVersion(latest);
      })
      .catch(() => {});
  }, []);

  return latestVersion;
}

const defaultOverview: Overview = {
  watcher_enabled: true,
  auto_resume: true,
  session_count: 0,
  waiting_count: 0,
  due_count: 0,
  next_reset_at: null,
  log_dir: "",
  state_dir: ""
};

const defaultSettings: WatchdogSettings = {
  poll_interval_seconds: 15,
  auto_resume: true,
  alert_mode: "dialog-sound-notification",
  sound_enabled: true,
  dialog_enabled: true,
  notification_enabled: true,
  max_retry_count: 3,
  watcher_enabled: true
};

function formatCountdown(value: string | null): string {
  if (!value) return "No limit hit";
  const delta = Math.round((new Date(value).getTime() - Date.now()) / 60000);
  if (delta <= 0) return "Ready to resume";
  if (delta < 60) return `Resets in ${delta}m`;
  const hours = Math.floor(delta / 60);
  const minutes = delta % 60;
  return `Resets in ${hours}h ${minutes}m`;
}

async function resizeWidget(width: number, height: number) {
  try {
    const appWindow = getCurrentWindow();
    await appWindow.setSize(new LogicalSize(width, height));
  } catch {
    // Keep the UI usable even when opened in a plain browser.
  }
}

async function startDragging() {
  try {
    await getCurrentWindow().startDragging();
  } catch {
    // Ignore outside of Tauri runtime.
  }
}

async function openSettingsWindow() {
  try {
    const existing = await WebviewWindow.getByLabel("settings");
    if (existing) {
      await existing.show();
      await existing.unminimize();
      await existing.setFocus();
      return;
    }

    const nextWindow = new WebviewWindow("settings", {
      url: "/#/settings",
      title: "Claude Watchdog Settings",
      width: 464,
      height: 580,
      minWidth: 464,
      minHeight: 540,
      center: true,
      resizable: true,
      decorations: true,
      transparent: false,
      focus: true
    });

    nextWindow.once("tauri://error", (event) => {
      console.error("Unable to open settings window", event);
    });
  } catch (issue) {
    console.error(issue);
  }
}

function GearIcon() {
  return (
    <svg aria-hidden="true" className="icon-gear" viewBox="0 0 24 24">
      <path d="M19.14 12.94a7.43 7.43 0 0 0 .05-.94 7.43 7.43 0 0 0-.05-.94l2.03-1.58a.48.48 0 0 0 .12-.62l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.08 7.08 0 0 0-1.63-.94L14.4 2.8a.49.49 0 0 0-.48-.4h-3.84a.49.49 0 0 0-.48.4L9.25 5.34c-.57.23-1.12.54-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.86a.48.48 0 0 0 .12.62l2.03 1.58a7.43 7.43 0 0 0-.05.94 7.43 7.43 0 0 0 .05.94L2.83 14.52a.48.48 0 0 0-.12.62l1.92 3.32c.13.22.39.31.6.22l2.39-.96c.5.4 1.05.72 1.63.94l.35 2.54c.04.24.24.4.48.4h3.84c.24 0 .44-.16.48-.4l.35-2.54c.57-.22 1.12-.54 1.63-.94l2.39.96c.22.09.47 0 .6-.22l1.92-3.32a.48.48 0 0 0-.12-.62l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z" />
    </svg>
  );
}

function Toggle({
  checked,
  onChange
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <label className="toggle-switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="toggle-slider" />
    </label>
  );
}

function SettingsRow({
  title,
  description,
  checked,
  onChange
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <div className="toggle-card">
      <div className="toggle-info">
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <Toggle checked={checked} onChange={onChange} />
    </div>
  );
}

function SettingsPage({
  overview,
  settings,
  setSettings,
  refresh
}: {
  overview: Overview;
  settings: WatchdogSettings;
  setSettings: (next: WatchdogSettings) => void;
  refresh: () => Promise<void>;
}) {
  const latestVersion = useUpdateCheck();

  async function saveSettings() {
    await api.saveSettings(settings);
    await refresh();
  }

  return (
    <main className="settings-page">
      <section className="settings-panel">
        <div className="settings-topbar">
          <h1 className="settings-title">Settings</h1>
          <span className="version-badge">v{CURRENT_VERSION}</span>
        </div>

        {latestVersion && (
          <a className="update-banner" href={RELEASES_URL} target="_blank" rel="noreferrer">
            <span className="update-dot" />
            v{latestVersion} available — click to download
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginLeft: 4}}><path d="M7 17L17 7M7 7h10v10"/></svg>
          </a>
        )}

        <div className="settings-body">
          <div className="settings-section">
            <p className="settings-section-label">Core</p>
            <SettingsRow
              title="Background Watcher"
              description="Monitor Terminal tabs every 15 s for credit exhaustion."
              checked={overview.watcher_enabled}
              onChange={(val) => void api.toggleWatcher(val).then(refresh)}
            />
            <SettingsRow
              title="Auto Resume"
              description='Send "Please continue…" to Claude when credits reset.'
              checked={settings.auto_resume}
              onChange={(val) => setSettings({ ...settings, auto_resume: val })}
            />
          </div>

          <div className="settings-section">
            <p className="settings-section-label">Alerts</p>
            <SettingsRow
              title="Notification"
              description="macOS notification banner when a session resets."
              checked={settings.notification_enabled}
              onChange={(val) => setSettings({ ...settings, notification_enabled: val })}
            />
            <SettingsRow
              title="Dialog"
              description="Blocking alert dialog — impossible to miss."
              checked={settings.dialog_enabled}
              onChange={(val) => setSettings({ ...settings, dialog_enabled: val })}
            />
            <SettingsRow
              title="Voice"
              description="Say it out loud via the system speech engine."
              checked={settings.sound_enabled}
              onChange={(val) => setSettings({ ...settings, sound_enabled: val })}
            />
          </div>
        </div>

        <div className="settings-footer">
          <button className="plain-link" onClick={() => void api.openLogDir()} type="button">
            Open logs
          </button>
          <button className="save-button" onClick={() => void saveSettings()} type="button">
            Save
          </button>
        </div>
      </section>
    </main>
  );
}

function Widget({
  overview,
  sessions,
  loading,
  error,
  refresh
}: {
  overview: Overview;
  sessions: SessionRecord[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}) {
  const limitedSessions = useMemo(
    () => sessions.filter((session) => session.status === "rate_limited"),
    [sessions]
  );

  const primarySession = limitedSessions[0] ?? null;
  const isLimited = overview.waiting_count > 0 || limitedSessions.length > 0;
  const statusLabel = isLimited ? "Credit locked" : "Claude ready";
  const detailLabel = isLimited
    ? formatCountdown(primarySession?.resets_at ?? overview.next_reset_at)
    : "No limit hit";

  return (
    <main className="widget-shell">
      <section
        className={`widget-card ${isLimited ? "is-limited" : "is-ready"}`}
        onMouseDown={() => void startDragging()}
      >
        <div className="widget-main">
          <div className={`status-dot ${isLimited ? "is-limited" : "is-ready"}`} />

          <div className="widget-copy">
            <p className="widget-title">{statusLabel}</p>
            <p className="widget-subtitle">{loading ? "Checking…" : error ? error : detailLabel}</p>
          </div>

          <div className="widget-actions">
            <button
              aria-label="Open settings"
              className="icon-chip"
              onClick={openSettingsWindow}
              onMouseDown={(event) => event.stopPropagation()}
              type="button"
            >
              <GearIcon />
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const [overview, setOverview] = useState<Overview>(defaultOverview);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [settings, setSettings] = useState<WatchdogSettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isSettingsPage = window.location.hash === "#/settings";

  async function refresh() {
    try {
      const [nextOverview, nextSessions, nextSettings] = await Promise.all([
        api.getOverview(),
        api.getSessions(),
        api.getSettings()
      ]);
      startTransition(() => {
        setOverview(nextOverview);
        setSessions(nextSessions);
        setSettings(nextSettings);
        setError(null);
        setLoading(false);
      });
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "Unable to read watchdog status");
      setLoading(false);
    }
  }

  // Auto-hide widget after 5 minutes of no interaction
  useEffect(() => {
    if (isSettingsPage) return;

    const TIMEOUT_MS = 5 * 60 * 1000;
    let hideTimer: number;

    const resetTimer = () => {
      clearTimeout(hideTimer);
      hideTimer = window.setTimeout(() => {
        getCurrentWindow().hide().catch(() => {});
      }, TIMEOUT_MS);
    };

    resetTimer();
    window.addEventListener("mousemove", resetTimer);
    window.addEventListener("mousedown", resetTimer);

    return () => {
      clearTimeout(hideTimer);
      window.removeEventListener("mousemove", resetTimer);
      window.removeEventListener("mousedown", resetTimer);
    };
  }, [isSettingsPage]);

  useEffect(() => {
    void refresh();

    if (isSettingsPage) {
      void resizeWidget(464, 580);
      void invoke("get_overview").catch(() => undefined);
    } else {
      void resizeWidget(196, 64);
    }

    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [isSettingsPage]);

  if (isSettingsPage) {
    return (
      <SettingsPage
        overview={overview}
        refresh={refresh}
        settings={settings}
        setSettings={setSettings}
      />
    );
  }

  return (
    <Widget
      error={error}
      loading={loading}
      overview={overview}
      refresh={refresh}
      sessions={sessions}
    />
  );
}
