import type { Overview } from "../lib/types";

function relativeTime(value: string | null): string {
  if (!value) return "暂无等待中的恢复时间";
  const target = new Date(value).getTime();
  const delta = Math.round((target - Date.now()) / 60000);
  if (delta <= 0) return "现在就可以恢复";
  if (delta < 60) return `还要 ${delta} 分钟`;
  const hours = Math.floor(delta / 60);
  const minutes = delta % 60;
  return `还要 ${hours} 小时 ${minutes} 分钟`;
}

export function OverviewHeader({
  overview,
  onToggle,
  onResumeDue
}: {
  overview: Overview;
  onToggle: () => void;
  onResumeDue: () => void;
}) {
  return (
    <section className="hero-card">
      <div className="hero-head">
        <div>
          <p className="eyebrow">状态总览</p>
          <h1>Claude Credit Watchdog</h1>
        </div>
        <button
          className={overview.watcher_enabled ? "ghost-button is-live" : "ghost-button"}
          onClick={onToggle}
          type="button"
        >
          {overview.watcher_enabled ? "监听中" : "已暂停"}
        </button>
      </div>

      <div className="hero-grid">
        <article>
          <span>下一次恢复时间</span>
          <strong>{relativeTime(overview.next_reset_at)}</strong>
        </article>
        <article>
          <span>等待恢复的会话</span>
          <strong>{overview.waiting_count}</strong>
        </article>
        <article>
          <span>现在可恢复</span>
          <strong>{overview.due_count}</strong>
        </article>
      </div>

      <div className="hero-actions">
        <button className="primary-button" onClick={onResumeDue} type="button">
          立即恢复所有到点会话
        </button>
      </div>
    </section>
  );
}
