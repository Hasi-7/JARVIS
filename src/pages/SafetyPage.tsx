import { SYSTEM } from '@/data/mock';
import { SystemRow } from '@/components/dashboard/SystemRow';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';

// What is actually enforced in this build today. These are real, code-backed
// controls — not aspirational copy.
const REAL_CONTROLS = [
  'Safe brain command allowlist (no arbitrary commands)',
  'No arbitrary shell execution',
  'Backup-before-write on every vault write workflow',
  'No external tool launches',
  'No Gmail mutations (no email integration at all)',
  'No Google Calendar API writes (.ics export only)',
  'No browser / computer-use actions',
  'Local agent has no tools (chat only)',
];

// Risk posture. "Active" = enforced today. "Not built" = the capability does not
// exist yet, so there is nothing to gate (shown grey, not as a working confirm gate).
const GUARDRAILS: { label: string; state: string; color: string }[] = [
  { label: 'Arbitrary shell execution',        state: 'Disabled',   color: 'var(--green)' },
  { label: 'Credential / secret access',       state: 'Disabled',   color: 'var(--green)' },
  { label: 'Payment / billing actions',        state: 'Disabled',   color: 'var(--green)' },
  { label: 'Brain CLI (allowlisted cmds)',     state: 'Allowed',    color: 'var(--live)' },
  { label: 'Low-risk vault reads',             state: 'Allowed',    color: 'var(--live)' },
  { label: 'Vault writes (backup-before-write)', state: 'Allowed',  color: 'var(--live)' },
  { label: 'External email send',              state: 'Not built',  color: 'var(--txt-3)' },
  { label: 'Google Calendar event creation',   state: 'Not built',  color: 'var(--txt-3)' },
  { label: 'Vault note deletion',              state: 'Not built',  color: 'var(--txt-3)' },
  { label: 'Browser / computer-use actions',   state: 'Not built',  color: 'var(--txt-3)' },
];

export function SafetyPage() {
  return (
    <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* honesty banner */}
      <div style={{
        padding: 'var(--s3) var(--s4)',
        background: 'var(--surface-2)',
        border: '1px solid var(--amber-line)',
        borderRadius: 'var(--r2)',
        fontSize: 12,
        color: 'var(--txt-1)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        lineHeight: 1.5,
      }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          Privileged agent tools are not enabled yet. Browser, computer-use, MCP, Gmail, and
          NemoClaw/OpenShell runtime enforcement are planned but not wired in this build. The runtime
          rows below show <strong>Not wired</strong> until those bridges exist.
        </span>
      </div>

      {/* planned runtimes — honest "not wired" status */}
      <div className="panel panel-pad">
        <PanelHeader icon="shield" title="Planned runtimes" sub="Not implemented in this build" />
        {[SYSTEM.nemoclaw, SYSTEM.openclaw, SYSTEM.browser, SYSTEM.computer, SYSTEM.mcp].map((svc, i) => (
          <SystemRow key={i} service={svc} />
        ))}
        <div style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 'var(--s3)', lineHeight: 1.5 }}>
          These are PRD-defined runtimes (§31, §32, §13). They are shown for transparency only — none
          of them run, enforce policy, or mediate any action in this build.
        </div>
      </div>

      {/* what is actually real today */}
      <div className="panel panel-pad">
        <PanelHeader icon="check" title="Current real safety controls" sub="Enforced in this build" />
        {REAL_CONTROLS.map((c, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '8px 0', borderBottom: i < REAL_CONTROLS.length - 1 ? '1px solid var(--line-soft)' : 'none' }}>
            <StatusDot tone="green" />
            <span style={{ flex: 1, fontSize: 12.5, color: 'var(--txt-0)' }}>{c}</span>
            <span style={{ fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--green)' }}>
              Active
            </span>
          </div>
        ))}
      </div>

      {/* risk posture */}
      <div className="panel panel-pad">
        <PanelHeader icon="shield" title="Risk posture" sub="Allowed / disabled / not built" />
        {GUARDRAILS.map((g, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '9px 0', borderBottom: i < GUARDRAILS.length - 1 ? '1px solid var(--line-soft)' : 'none' }}>
            <div style={{ flex: 1, fontSize: 12.5, color: 'var(--txt-0)' }}>{g.label}</div>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: g.color }}>
              {g.state}
            </span>
          </div>
        ))}
      </div>

      {/* tool log — honest about not existing yet */}
      <div className="panel panel-pad">
        <PanelHeader icon="layers" title="Tool / action log" sub="Planned" />
        <div style={{ fontSize: 12, color: 'var(--txt-2)', lineHeight: 1.5 }}>
          Tool/action logging (<span className="mono" style={{ fontSize: 11 }}>ops/tool-logs/</span>) is
          planned but not implemented. No agent tools run in this build, so there are no tool calls to log.
        </div>
      </div>

    </div>
  );
}
