// Read-only runtime readiness UI (OpenClaw / NemoClaw Runtime Status v0).
// Display only — no connect/start/test/enable controls. Nothing launches or executes.

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeStatusItem, NemoclawProbeResponse } from '@/lib/api';
import {
  runtimeStatusLabel, runtimeStatusTone, isBlocked,
  probeStatusLabel, probeStatusTone, RUNTIME_TRUTHS, PROBE_COPY,
} from '@/lib/runtimeStatus';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';

// ── compact rows (Dashboard) ────────────────────────────────────────────────────

export function RuntimeStatusRows({ items }: { items: RuntimeStatusItem[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 4 }}>
      {items.map((item) => (
        <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--txt-1)', minWidth: 0 }}>
            <StatusDot tone={runtimeStatusTone(item)} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
          </span>
          <span style={{
            flexShrink: 0, fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em',
            color: runtimeStatusTone(item) === 'amber' ? 'var(--amber)'
                 : runtimeStatusTone(item) === 'green' ? 'var(--green)'
                 : runtimeStatusTone(item) === 'red' ? 'var(--red)' : 'var(--txt-3)',
          }}>
            {runtimeStatusLabel(item)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── NemoClaw/OpenShell health probe (explicit, opt-in) ──────────────────────────

function tinyTimeAgo(iso: string): string {
  try { return new Date(iso).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false }); }
  catch { return ''; }
}

function NemoclawProbePanel() {
  const [result, setResult] = useState<NemoclawProbeResponse | null>(null);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the cached last probe on mount — this is NOT a probe (no network call).
  useEffect(() => {
    let alive = true;
    api.getLastNemoclawProbe()
      .then((r) => { if (alive && r.lastProbe) setResult(r.lastProbe); })
      .catch(() => { /* non-fatal — leave empty */ });
    return () => { alive = false; };
  }, []);

  const probe = useCallback(async () => {
    setProbing(true);
    setError(null);
    try {
      const r = await api.probeNemoclawRuntime();   // explicit, user-triggered only
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Probe failed.');
    } finally {
      setProbing(false);
    }
  }, []);

  return (
    <div style={{
      marginBottom: 'var(--s3)', padding: '9px 11px', borderRadius: 'var(--r2)',
      border: '1px solid var(--line)', background: 'var(--surface-2)',
      display: 'flex', flexDirection: 'column', gap: 7,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)' }}>NemoClaw/OpenShell health probe</span>
        <button className="btn btn-sm btn-ghost" onClick={probe} disabled={probing} style={{ fontSize: 11 }}>
          <Icon name={probing ? 'sync' : 'shield'} size={12} style={{ animation: probing ? 'spin 1s linear infinite' : undefined }} />
          {probing ? 'Checking…' : 'Check NemoClaw/OpenShell'}
        </button>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
        {PROBE_COPY.what}
      </div>

      {error && (
        <div style={{ fontSize: 10.5, color: 'var(--red)' }}>{error}</div>
      )}

      {result && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10.5,
          paddingTop: 6, borderTop: '1px solid var(--line-soft)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <StatusDot tone={probeStatusTone(result.status)} />
            <span style={{ fontWeight: 600, color:
              probeStatusTone(result.status) === 'green' ? 'var(--green)'
              : probeStatusTone(result.status) === 'amber' ? 'var(--amber)'
              : probeStatusTone(result.status) === 'red' ? 'var(--red)' : 'var(--txt-2)',
            }}>
              {probeStatusLabel(result.status)}
            </span>
            <span style={{ color: 'var(--txt-3)' }}>· checked {tinyTimeAgo(result.checkedAt)} · {result.durationMs}ms</span>
          </div>
          <div style={{ color: 'var(--txt-2)', lineHeight: 1.4 }}>{result.message}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, color: 'var(--txt-3)' }}>
            <span>URL configured: {result.details.urlConfigured ? 'yes' : 'no'}</span>
            <span>Policy path: {result.details.policyPathConfigured ? 'yes' : 'no'}</span>
            {result.details.hostRedacted && (
              <span className="mono">host {result.details.hostRedacted}</span>
            )}
          </div>
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--amber)', lineHeight: 1.4 }}>
        {PROBE_COPY.stillDisabled}
      </div>
    </div>
  );
}

// ── full guardrail section (Tool Connections) ───────────────────────────────────

function nameFor(id: string, items: RuntimeStatusItem[]): string {
  return items.find((i) => i.id === id)?.name ?? id;
}

export function RuntimeGuardrails({ items, degraded, loading }: {
  items: RuntimeStatusItem[];
  degraded: boolean;
  loading: boolean;
}) {
  return (
    <div className="panel panel-pad" style={{ marginTop: 'var(--s4)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--s3)' }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)' }}>Runtime Guardrails</span>
        {loading && <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>· loading…</span>}
        {degraded && (
          <span style={{ fontSize: 10.5, color: 'var(--amber)' }}>· backend unreachable — showing fallback</span>
        )}
      </div>

      <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5, marginBottom: 'var(--s3)' }}>
        {RUNTIME_TRUTHS.notWired} {RUNTIME_TRUTHS.browserBlocked}
      </div>

      {/* explicit, opt-in NemoClaw/OpenShell reachability probe — unlocks nothing */}
      <NemoclawProbePanel />

      {/* dependency chain — read-only */}
      <div className="mono" style={{
        fontSize: 10.5, color: 'var(--txt-3)', background: 'var(--surface-2)',
        border: '1px solid var(--line)', borderRadius: 'var(--r2)', padding: '7px 9px',
        marginBottom: 'var(--s3)', lineHeight: 1.5, whiteSpace: 'pre-wrap',
      }}>
        OpenClaw → NemoClaw/OpenShell → Permission Gateway → approved tools
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
        {items.map((item) => (
          <div key={item.id} style={{
            padding: '8px 10px', border: '1px solid var(--line-soft)', borderRadius: 'var(--r2)',
            background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot tone={runtimeStatusTone(item)} />
              <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--txt-0)', flex: 1 }}>{item.name}</span>
              <span style={{
                fontSize: 9.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em',
                color: runtimeStatusTone(item) === 'amber' ? 'var(--amber)'
                     : runtimeStatusTone(item) === 'green' ? 'var(--green)'
                     : runtimeStatusTone(item) === 'red' ? 'var(--red)' : 'var(--txt-3)',
              }}>
                {runtimeStatusLabel(item)}
              </span>
              {/* read-only: no connect/start/test. Mirrors Tool Connections "Not wired yet". */}
              <button className="btn btn-sm" disabled style={{ fontSize: 9.5, padding: '2px 7px', opacity: 0.5, cursor: 'not-allowed' }}>
                Not wired yet
              </button>
            </div>

            {item.requiredFor.length > 0 && (
              <div style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
                <span style={{ color: 'var(--txt-3)' }}>Would unlock: </span>{item.requiredFor.join(' · ')}
              </div>
            )}
            {item.dependsOn.length > 0 && (
              <div style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
                Depends on: {item.dependsOn.map((d) => nameFor(d, items)).join(', ')}
              </div>
            )}
            {item.blocks.length > 0 && (
              <div style={{ fontSize: 10.5, color: isBlocked(item) ? 'var(--amber)' : 'var(--txt-3)', lineHeight: 1.45 }}>
                <span style={{ fontWeight: 600 }}>Blocked: </span>{item.blocks.join(' · ')}
              </div>
            )}
            {item.notes && (
              <div style={{ fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.4 }}>{item.notes}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── small inline note (Local Agent) ─────────────────────────────────────────────

export function RuntimeGuardrailNote({ items }: { items: RuntimeStatusItem[] }) {
  const nemo = items.find((i) => i.id === 'nemoclaw_openshell');
  const openclaw = items.find((i) => i.id === 'openclaw');
  const nemoLabel = nemo ? runtimeStatusLabel(nemo) : 'Not configured';
  const openclawLabel = openclaw ? runtimeStatusLabel(openclaw) : 'Not wired';

  return (
    <div className="panel panel-pad">
      <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Runtime guardrail</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ color: 'var(--txt-2)' }}>NemoClaw/OpenShell</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--txt-1)', fontWeight: 500 }}>
            <StatusDot tone={nemo ? runtimeStatusTone(nemo) : 'grey'} />{nemoLabel}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ color: 'var(--txt-2)' }}>OpenClaw bridge</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--txt-1)', fontWeight: 500 }}>
            <StatusDot tone={openclaw ? runtimeStatusTone(openclaw) : 'grey'} />{openclawLabel}
          </span>
        </div>
      </div>
      <div style={{
        marginTop: 'var(--s2)', paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)',
        fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.45,
      }}>
        Agent remains local chat + evaluate-only tool requests. No mode executes tools from chat.
      </div>
    </div>
  );
}
