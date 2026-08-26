/**
 * Tool Safety — PRD §31.
 *
 * This page used to be entirely static, and had drifted into asserting things
 * that are no longer true: that there was no email integration, that the local
 * agent had no tools, that browser/computer-use were "not built", and that tool
 * logging was "planned but not implemented". All four had shipped.
 *
 * Everything here now derives from the backend. The one hardcoded list left is
 * PERMANENT_REFUSALS, which describes code paths that do not exist — and each
 * entry names the file that makes it true, so it can be re-verified.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ToolConnectionStatus } from '@/lib/api';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';
import { PermissionLogPanel } from '@/components/tools/PermissionLogPanel';
import { RuntimeStatusRows } from '@/components/runtime/RuntimeStatus';
import { useRuntimeStatus } from '@/lib/runtimeStatus';

/**
 * Capabilities with NO code path at all — not "disabled by a flag", but absent.
 * Each names the source that makes it true so this list stays checkable rather
 * than becoming the next piece of stale copy.
 */
const PERMANENT_REFUSALS: { label: string; why: string }[] = [
  { label: 'Arbitrary shell execution',
    why: 'brain.py runs an allowlisted argv with shell=False; openshell_exec allows curl only.' },
  { label: 'Gmail send / delete / label changes',
    why: 'gmail.py issues GET requests only; no mutation method exists.' },
  { label: 'Calendar event update / move / delete',
    why: 'gcal_write.py implements insert only, with sendUpdates=none and no attendees.' },
  { label: 'Google Drive create / update / delete / share',
    why: 'gdrive.py is read-only (drive.readonly scope).' },
  { label: 'GitHub write / merge / comment',
    why: 'github.py issues GET requests only.' },
  { label: 'Canvas/Quercus submission',
    why: 'quercus.py is GET-only; assignment submission is deliberately out of scope.' },
  { label: 'Typing into a credential window',
    why: 'computer_use.py refuses outright — it cannot be confirmed away.' },
  { label: 'Unsandboxed page fetching',
    why: 'browser.sandboxed_fetch fails closed when the guardrail is unhealthy; there is no fallback.' },
];

function statusTone(status: string, enabled: boolean): 'green' | 'amber' | 'red' | 'grey' {
  if (status === 'available' && enabled) return 'green';
  if (status === 'error' || status === 'unavailable') return 'red';
  if (status === 'not_configured') return 'amber';
  return 'grey';
}

function riskColor(risk: string): string {
  if (risk === 'high' || risk === 'disabled') return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--green)';
}

function ToolRow({ t }: { t: ToolConnectionStatus }) {
  const tone = statusTone(t.status, t.enabled);
  return (
    <div style={{ padding: 'var(--s3) 0', borderBottom: '1px solid var(--line-soft)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap' }}>
        <StatusDot tone={tone} />
        <span style={{ fontSize: 12.5, color: 'var(--txt-0)', fontWeight: 600 }}>{t.name}</span>
        <span style={{ fontSize: 10, color: riskColor(t.riskLevel), fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {t.riskLevel}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                       color: tone === 'green' ? 'var(--green)' : tone === 'red' ? 'var(--red)' : tone === 'amber' ? 'var(--amber)' : 'var(--txt-3)' }}>
          {t.status.replace(/_/g, ' ')}
        </span>
      </div>
      {t.allowedNow.length > 0 && (
        <div style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 4 }}>
          <span style={{ color: 'var(--green)' }}>allowed</span>{' '}
          <span className="mono">{t.allowedNow.join(', ')}</span>
        </div>
      )}
      {t.blockedNow.length > 0 && (
        <div style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 2 }}>
          <span style={{ color: 'var(--txt-3)' }}>blocked</span>{' '}
          <span className="mono">{t.blockedNow.join(', ')}</span>
        </div>
      )}
      {t.notes && (
        <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 4, lineHeight: 1.45 }}>{t.notes}</div>
      )}
    </div>
  );
}

export function SafetyPage() {
  const [tools, setTools] = useState<ToolConnectionStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const runtime = useRuntimeStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getToolConnectionStatus();
      setTools(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tool status.');
      setTools([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const active = (tools ?? []).filter((t) => t.status === 'available' && t.enabled);
  const inactive = (tools ?? []).filter((t) => !(t.status === 'available' && t.enabled));

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--s3)', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Tool Safety</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            live status · every value on this page comes from the backend
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
        </div>
      )}

      {/* what can act right now */}
      <div className="panel panel-pad">
        <PanelHeader
          icon="bolt"
          title="Capabilities active right now"
          sub={tools === null ? 'loading…' : `${active.length} of ${tools.length} tools`}
        />
        {tools === null ? (
          <div style={{ textAlign: 'center', padding: 'var(--s6)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
        ) : active.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--txt-2)', lineHeight: 1.5 }}>
            No privileged tool is currently active. Read-only vault and brain-status access remain
            available.
          </div>
        ) : (
          active.map((t) => <ToolRow key={t.id} t={t} />)
        )}
      </div>

      {/* runtime */}
      <div className="panel panel-pad">
        <PanelHeader icon="shield" title="Runtime guardrails" sub="OpenClaw · NemoClaw/OpenShell · harnesses" />
        {runtime.items.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--txt-3)' }}>Loading runtime status…</div>
        ) : (
          <RuntimeStatusRows items={runtime.items} />
        )}
        {runtime.degraded && (
          <div style={{ fontSize: 10.5, color: 'var(--amber)', marginTop: 'var(--s3)', lineHeight: 1.45 }}>
            Runtime status could not be read from the backend; the rows above are the safe
            fallback and may understate what is configured.
          </div>
        )}
      </div>

      {/* off or unconfigured */}
      <div className="panel panel-pad">
        <PanelHeader
          icon="layers"
          title="Off or not configured"
          sub="present in the build, not currently able to act"
        />
        {tools === null ? (
          <div style={{ textAlign: 'center', padding: 'var(--s5)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
        ) : inactive.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--txt-3)' }}>Every registered tool is active.</div>
        ) : (
          inactive.map((t) => <ToolRow key={t.id} t={t} />)
        )}
      </div>

      {/* permanent refusals */}
      <div className="panel panel-pad">
        <PanelHeader
          icon="shield"
          title="Permanently refused"
          sub="no code path exists — not a toggle"
        />
        {PERMANENT_REFUSALS.map((r, i) => (
          <div key={r.label} style={{ padding: '9px 0', borderBottom: i < PERMANENT_REFUSALS.length - 1 ? '1px solid var(--line-soft)' : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)' }}>
              <StatusDot tone="green" />
              <span style={{ flex: 1, fontSize: 12.5, color: 'var(--txt-0)' }}>{r.label}</span>
              <span style={{ fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--green)' }}>
                Refused
              </span>
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3, paddingLeft: 15, lineHeight: 1.45 }}>{r.why}</div>
          </div>
        ))}
      </div>

      {/* the real audit trail */}
      <PermissionLogPanel limit={25} />

      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'flex-start', gap: 6, lineHeight: 1.5 }}>
        <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>
          Privileged execution additionally requires <span className="mono">BRAIN_UI_PRIVILEGED_EXECUTION_ENABLED</span>,
          an operator token, Assist mode, and separate approve and execute confirmations. Computer-use
          requires its own kill switch on top of all of that.
        </span>
      </div>

    </div>
  );
}
