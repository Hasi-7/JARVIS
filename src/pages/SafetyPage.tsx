import { SYSTEM } from '@/data/mock';
import { SystemRow } from '@/components/dashboard/SystemRow';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { Icon } from '@/components/ui/Icon';

const GUARDRAILS = [
  { label: 'Arbitrary shell execution', state: 'Disabled', color: 'var(--green)' },
  { label: 'Credential / secret access', state: 'Disabled', color: 'var(--green)' },
  { label: 'Payment / billing actions', state: 'Disabled', color: 'var(--green)' },
  { label: 'Vault file deletion', state: 'Requires confirm', color: 'var(--amber)' },
  { label: 'External email send', state: 'Requires confirm', color: 'var(--amber)' },
  { label: 'Calendar event creation', state: 'Requires confirm', color: 'var(--amber)' },
  { label: 'Low-risk vault reads', state: 'Allowed', color: 'var(--live)' },
  { label: 'Brain CLI (allowlisted cmds)', state: 'Allowed', color: 'var(--live)' },
];

export function SafetyPage() {
  return (
    <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div className="panel panel-pad">
        <PanelHeader icon="shield" title="Runtime status" sub="OpenClaw security stack" />
        {[SYSTEM.nemoclaw, SYSTEM.browser, SYSTEM.computer, SYSTEM.mcp].map((svc, i) => (
          <SystemRow key={i} service={svc} />
        ))}
      </div>

      <div className="panel panel-pad">
        <PanelHeader
          icon="shield"
          title="Policy guardrails"
          right={
            <button className="btn btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red-line)', background: 'var(--red-bg)' }}>
              <Icon name="x" size={13} />Emergency lock
            </button>
          }
        />
        {GUARDRAILS.map((g, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '9px 0', borderBottom: '1px solid var(--line-soft)' }}>
            <div style={{ flex: 1, fontSize: 12.5, color: 'var(--txt-0)' }}>{g.label}</div>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: g.color }}>
              {g.state}
            </span>
          </div>
        ))}
      </div>

      <div className="panel panel-pad">
        <PanelHeader icon="layers" title="Recent tool calls" sub="Last 24 hours" />
        <div style={{ fontSize: 12, color: 'var(--txt-2)', fontStyle: 'italic' }}>
          Tool call log will appear here once backend is connected.
        </div>
      </div>

    </div>
  );
}
