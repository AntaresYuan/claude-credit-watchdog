import { invoke } from "@tauri-apps/api/core";
import type { Overview, SessionRecord, WatchdogSettings } from "./types";

export const api = {
  getSessions: () => invoke<SessionRecord[]>("get_sessions"),
  getOverview: () => invoke<Overview>("get_overview"),
  resumeSession: (sessionId: string) => invoke("resume_session", { sessionId }),
  resumeDueSessions: () => invoke("resume_due_sessions"),
  dismissAlert: (sessionId: string) => invoke("dismiss_alert", { sessionId }),
  toggleWatcher: (enabled: boolean) => invoke<WatchdogSettings>("toggle_watcher", { enabled }),
  getSettings: () => invoke<WatchdogSettings>("get_settings"),
  saveSettings: (settings: WatchdogSettings) => invoke<WatchdogSettings>("save_settings", { settings }),
  openLogDir: () => invoke("open_log_dir")
};

