import type { SessionRecord } from "../lib/types";

function formatRelative(value?: string | null): string {
  if (!value) return "还没有拿到恢复时间";
  const delta = Math.round((new Date(value).getTime() - Date.now()) / 60000);
  if (delta <= 0) return "现在可以恢复";
  if (delta < 60) return `${delta} 分钟后`;
  return `${Math.floor(delta / 60)} 小时 ${delta % 60} 分钟后`;
}

function nicePath(cwd: string): string {
  const parts = cwd.split("/");
  return parts.slice(-3).join("/") || cwd;
}

export function SessionCard({
  session,
  onResume,
  onDismiss
}: {
  session: SessionRecord;
  onResume: () => void;
  onDismiss: () => void;
}) {
  return (
    <article className={`session-card status-${session.status}`}>
      <div className="session-main">
        <div className="session-copy">
          <div className="session-row">
            <span className="session-path">{nicePath(session.cwd)}</span>
            <span className="status-pill">
              {session.status === "active"
                ? "正常"
                : session.status === "rate_limited"
                  ? "额度耗尽"
                  : session.status === "resumed"
                    ? "已恢复"
                    : session.status === "stale"
                      ? "终端失效"
                      : "已关闭"}
            </span>
          </div>
          <p className="session-meta">
            <span>{session.tty || "没有 TTY"}</span>
            <span>{session.detection_source || "来源未知"}</span>
          </p>
          <p className="session-timer">恢复时间：{formatRelative(session.resets_at)}</p>
          {session.error_summary ? <p className="session-error">{session.error_summary}</p> : null}
        </div>
        <div className="session-actions">
          <button className="primary-button" onClick={onResume} type="button">
            立即发 `/resume`
          </button>
          <button className="ghost-button" onClick={onDismiss} type="button">
            忽略这轮提醒
          </button>
        </div>
      </div>
    </article>
  );
}
