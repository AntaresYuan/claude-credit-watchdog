import type { WatchdogSettings } from "../lib/types";

export function SettingsPanel({
  settings,
  onChange,
  onSave,
  onOpenLogs
}: {
  settings: WatchdogSettings;
  onChange: (next: WatchdogSettings) => void;
  onSave: () => void;
  onOpenLogs: () => void;
}) {
  return (
    <section className="settings-card">
      <div className="panel-head">
        <div>
          <p className="eyebrow">设置</p>
          <h2>恢复策略</h2>
        </div>
        <button className="ghost-button" onClick={onOpenLogs} type="button">
          打开日志目录
        </button>
      </div>

      <div className="setting-grid">
        <label>
          轮询间隔（秒）
          <input
            min={5}
            step={5}
            type="number"
            value={settings.poll_interval_seconds}
            onChange={(event) =>
              onChange({
                ...settings,
                poll_interval_seconds: Number(event.target.value)
              })
            }
          />
        </label>
        <label>
          最多重试次数
          <input
            min={1}
            max={10}
            type="number"
            value={settings.max_retry_count}
            onChange={(event) =>
              onChange({
                ...settings,
                max_retry_count: Number(event.target.value)
              })
            }
          />
        </label>
      </div>

      <div className="toggle-list">
        <label>
          <input
            checked={settings.auto_resume}
            type="checkbox"
            onChange={(event) => onChange({ ...settings, auto_resume: event.target.checked })}
          />
          到点后自动给 Claude 发 `/resume`
        </label>
        <label>
          <input
            checked={settings.notification_enabled}
            type="checkbox"
            onChange={(event) =>
              onChange({ ...settings, notification_enabled: event.target.checked })
            }
          />
          系统通知
        </label>
        <label>
          <input
            checked={settings.dialog_enabled}
            type="checkbox"
            onChange={(event) => onChange({ ...settings, dialog_enabled: event.target.checked })}
          />
          弹窗提醒
        </label>
        <label>
          <input
            checked={settings.sound_enabled}
            type="checkbox"
            onChange={(event) => onChange({ ...settings, sound_enabled: event.target.checked })}
          />
          声音提醒
        </label>
      </div>

      <button className="primary-button" onClick={onSave} type="button">
        保存设置
      </button>
    </section>
  );
}
