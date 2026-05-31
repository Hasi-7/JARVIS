import { APP_CONFIG } from '@/data/mock';
import { Icon } from '@/components/ui/Icon';

function ConfigRow({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', padding: 'var(--s4) 0', borderBottom: '1px solid var(--line-soft)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 12,
          color: 'var(--txt-1)',
          background: 'var(--surface-2)',
          padding: '8px 12px',
          borderRadius: 'var(--r2)',
          border: '1px solid var(--line)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </div>
      {note && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>{note}</div>
      )}
    </div>
  );
}

export function SettingsPage() {
  return (
    <div style={{ maxWidth: 560, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* paths */}
      <div className="panel panel-pad">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 'var(--s4)', color: 'var(--txt-0)' }}>
          Paths
        </div>
        <ConfigRow
          label="Vault path"
          value={APP_CONFIG.vaultPath}
          note="Mock value — will be resolved from brain vault-path once the backend is connected."
        />
        <ConfigRow
          label="brain CLI"
          value={APP_CONFIG.brainCmd}
          note="Mock value — will be read from backend config once the backend is connected."
        />
        <div style={{ paddingTop: 'var(--s4)' }} />
      </div>

      {/* backend */}
      <div className="panel panel-pad">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 'var(--s4)', color: 'var(--txt-0)' }}>
          Backend
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--s3)',
            padding: 'var(--s4)',
            borderRadius: 'var(--r2)',
            background: 'var(--surface-2)',
            border: '1px solid var(--line)',
          }}
        >
          <Icon name="shield" size={16} style={{ color: 'var(--txt-2)', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--txt-1)' }}>
              FastAPI backend — not yet connected
            </div>
            <div style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 2 }}>
              Runtime values (vault path, brain.cmd, OpenClaw status) are currently mocked.
              Real values will come from backend endpoints once the backend is implemented.
            </div>
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
            ['Version',     'v0.1.0 — frontend foundation'],
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
