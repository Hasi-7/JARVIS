import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { DEFAULTS } from '@/lib/config';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

type SyncState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'synced' }
  | { kind: 'local-only' }
  | { kind: 'rejected'; message: string };

function PathInput({
  label,
  value,
  onChange,
  error,
  warning,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  warning?: string;
  disabled?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', padding: 'var(--s4) 0', borderBottom: '1px solid var(--line-soft)' }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </label>
      <input
        className="mono"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        disabled={disabled}
        style={{
          fontSize: 12,
          color: disabled ? 'var(--txt-2)' : 'var(--txt-0)',
          background: 'var(--surface-2)',
          padding: '8px 12px',
          borderRadius: 'var(--r2)',
          border: `1px solid ${error ? 'var(--red)' : 'var(--line)'}`,
          fontFamily: 'var(--font-mono)',
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          opacity: disabled ? 0.6 : 1,
        }}
      />
      {error && <div style={{ fontSize: 11, color: 'var(--red)' }}>{error}</div>}
      {!error && warning && <div style={{ fontSize: 11, color: 'var(--amber)' }}>{warning}</div>}
    </div>
  );
}

export function SettingsPage() {
  const settings             = useAppStore((s) => s.settings);
  const updateSettings       = useAppStore((s) => s.updateSettings);
  const resetSettings        = useAppStore((s) => s.resetSettings);
  const syncConfigToBackend  = useAppStore((s) => s.syncConfigToBackend);
  const backendStatus        = useAppStore((s) => s.backendStatus);
  const backendConfig        = useAppStore((s) => s.backendConfig);

  const [draft, setDraft]       = useState({ ...settings });
  const [errors, setErrors]     = useState<Record<string, string>>({});
  const [syncState, setSyncState] = useState<SyncState>({ kind: 'idle' });

  const validate = (d: typeof draft) => {
    const e: Record<string, string> = {};
    if (!d.vaultPath.trim()) e.vaultPath = 'Vault path cannot be empty.';
    if (!d.brainCmd.trim())  e.brainCmd  = 'brain.cmd path cannot be empty.';
    return e;
  };

  const brainCmdWarning =
    draft.brainCmd.trim() && !draft.brainCmd.toLowerCase().endsWith('brain.cmd')
      ? 'Path does not end with brain.cmd — double-check this.'
      : undefined;

  const isSaving = syncState.kind === 'saving';

  const handleSave = async () => {
    const e = validate(draft);
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    const trimmed = { vaultPath: draft.vaultPath.trim(), brainCmd: draft.brainCmd.trim() };
    setSyncState({ kind: 'saving' });

    // Always save locally first
    updateSettings(trimmed);

    // Then attempt backend sync
    try {
      await syncConfigToBackend(trimmed);
      setSyncState({ kind: 'synced' });
    } catch (err) {
      if (backendStatus === 'error' || backendStatus === 'unknown') {
        setSyncState({ kind: 'local-only' });
      } else {
        setSyncState({
          kind: 'rejected',
          message: err instanceof Error ? err.message : 'Unknown error.',
        });
      }
    }
  };

  const handleReset = async () => {
    resetSettings();
    setDraft({ ...DEFAULTS });
    setErrors({});
    setSyncState({ kind: 'saving' });

    try {
      await syncConfigToBackend(DEFAULTS);
      setSyncState({ kind: 'synced' });
    } catch {
      setSyncState({ kind: 'local-only' });
    }
  };

  const syncColor =
    syncState.kind === 'synced'   ? 'var(--green)'  :
    syncState.kind === 'local-only' ? 'var(--amber)' :
    syncState.kind === 'rejected' ? 'var(--red)'    : 'var(--txt-2)';

  const syncText =
    syncState.kind === 'synced'     ? 'Saved locally and synced to backend.' :
    syncState.kind === 'local-only' ? 'Saved locally only — backend unavailable.' :
    syncState.kind === 'rejected'   ? `Backend rejected config: ${syncState.message}` :
    syncState.kind === 'saving'     ? 'Saving…' : '';

  // Backend section: dot tone + label
  const backendDotTone =
    backendStatus === 'ok'      ? 'green' as const :
    backendStatus === 'error'   ? 'red'   as const :
                                  'grey'  as const;

  const backendLabel =
    backendStatus === 'ok'    ? 'FastAPI backend · connected · localhost:8000' :
    backendStatus === 'error' ? 'FastAPI backend · not connected' :
                                'FastAPI backend · checking…';

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* paths */}
      <div className="panel panel-pad">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 'var(--s2)', color: 'var(--txt-0)' }}>
          Paths
        </div>
        <div style={{ fontSize: 11, color: 'var(--txt-3)', marginBottom: 'var(--s4)', lineHeight: 1.55 }}>
          {backendStatus === 'ok'
            ? <>Saved to localStorage and persisted to <span className="mono" style={{ fontSize: 10 }}>backend/data/brain-ui-config.json</span>. Backend config survives restarts.</>
            : <>Saved to localStorage. Will persist to <span className="mono" style={{ fontSize: 10 }}>backend/data/brain-ui-config.json</span> when backend connects.</>}
        </div>

        <PathInput
          label="Vault path"
          value={draft.vaultPath}
          onChange={(v) => { setDraft((d) => ({ ...d, vaultPath: v })); setSyncState({ kind: 'idle' }); }}
          error={errors.vaultPath}
          disabled={isSaving}
        />
        <PathInput
          label="brain CLI path"
          value={draft.brainCmd}
          onChange={(v) => { setDraft((d) => ({ ...d, brainCmd: v })); setSyncState({ kind: 'idle' }); }}
          error={errors.brainCmd}
          warning={brainCmdWarning}
          disabled={isSaving}
        />

        <div style={{ display: 'flex', gap: 'var(--s2)', marginTop: 'var(--s4)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={isSaving}>
            <Icon name="check" size={14} />Save
          </button>
          <button className="btn" onClick={handleReset} disabled={isSaving}>
            Reset to defaults
          </button>
          {syncText && (
            <span style={{ fontSize: 11, color: syncColor, display: 'flex', alignItems: 'center', gap: 5 }}>
              {syncState.kind === 'synced'     && <Icon name="check"  size={12} />}
              {syncState.kind === 'local-only' && <Icon name="shield" size={12} />}
              {syncState.kind === 'rejected'   && <Icon name="shield" size={12} />}
              {syncText}
            </span>
          )}
        </div>
      </div>

      {/* backend */}
      <div className="panel panel-pad">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 'var(--s4)', color: 'var(--txt-0)' }}>
          Backend
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 'var(--s3)',
            padding: 'var(--s4)',
            borderRadius: 'var(--r2)',
            background: 'var(--surface-2)',
            border: '1px solid var(--line)',
          }}
        >
          <span style={{ marginTop: 3, flexShrink: 0, lineHeight: 0 }}>
            <StatusDot tone={backendDotTone} pulse={backendStatus === 'ok'} />
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--txt-1)' }}>
              {backendLabel}
            </div>

            {backendStatus === 'ok' && backendConfig && (
              <div style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span>
                  brain.cmd — {backendConfig.brainCmdExists ? '✓ found' : '✗ not found at configured path'}
                </span>
                <span>
                  vault — {backendConfig.vaultPathExists ? '✓ found' : '✗ not found at configured path'}
                </span>
                {backendConfig.configSource && (
                  <span>
                    config source — <span className="mono" style={{ fontSize: 10 }}>{backendConfig.configSource}</span>
                    {backendConfig.configPersisted === false && backendConfig.configSource !== 'runtime' && (
                      <span style={{ color: 'var(--amber)', marginLeft: 6 }}>· not yet persisted to file</span>
                    )}
                  </span>
                )}
                {backendConfig.configWarning && (
                  <span style={{ color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="shield" size={11} />{backendConfig.configWarning}
                  </span>
                )}
              </div>
            )}

            {backendStatus === 'error' && (
              <div style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 4 }}>
                Start uvicorn to enable backend sync and brain command execution.
                Settings are saved to localStorage and will sync on next connect.
              </div>
            )}

            {backendStatus === 'unknown' && (
              <div style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 4 }}>
                Checking connection…
              </div>
            )}
          </div>
        </div>
      </div>

      {/* version / build */}
      <div className="panel panel-pad">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 'var(--s4)', color: 'var(--txt-0)' }}>
          Build info
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          {[
            ['Version',     'v0.1.0'],
            ['Agent',       'OpenClaw (mock — not connected)'],
            ['Security',    'NemoClaw / OpenShell (mock — not connected)'],
            ['Accent',      'Azure · oklch(0.74 0.115 218)'],
            ['Sphere style','Orb'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 'var(--s4)', fontSize: 12 }}>
              <span style={{ color: 'var(--txt-2)', width: 100, flexShrink: 0 }}>{k}</span>
              <span className="mono" style={{ color: 'var(--txt-1)' }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
