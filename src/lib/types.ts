export type SessionStatus = "active" | "rate_limited" | "resumed" | "stale" | "closed";

export interface SessionRecord {
  session_id: string;
  tty: string;
  cwd: string;
  status: SessionStatus;
  detection_source?: string;
  started_at?: string;
  last_seen_at?: string;
  resets_at?: string | null;
  last_resume_at?: string | null;
  resume_attempts: number;
  error_summary?: string | null;
  dismissed_for_reset?: string | null;
  used_percentage?: number;
}

export interface Overview {
  watcher_enabled: boolean;
  auto_resume: boolean;
  session_count: number;
  waiting_count: number;
  due_count: number;
  next_reset_at: string | null;
  log_dir: string;
  state_dir: string;
}

export interface WatchdogSettings {
  poll_interval_seconds: number;
  auto_resume: boolean;
  alert_mode: string;
  sound_enabled: boolean;
  dialog_enabled: boolean;
  notification_enabled: boolean;
  max_retry_count: number;
  watcher_enabled: boolean;
}

