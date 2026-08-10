// Read-only runtime readiness UI (OpenClaw / NemoClaw Runtime Status v0).
// Display only — no connect/start/test/enable controls. Nothing launches or executes.

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeStatusItem, NemoclawProbeResponse, NemoclawPolicyResponse, GuardrailReadinessResponse, RuntimeBridgeValidationResponse } from '@/lib/api';
import {
  runtimeStatusLabel, runtimeStatusTone, isBlocked,
  probeStatusLabel, probeStatusTone, RUNTIME_TRUTHS, PROBE_COPY,
  policyStatusLabel, policyStatusTone, capabilityLabel, capabilityTone, POLICY_COPY,
  readinessStatusLabel, readinessStatusTone, READINESS_COPY,
  bridgeStatusLabel, bridgeStatusTone, riskTone, BRIDGE_ACTION_KINDS, BRIDGE_COPY,
} from '@/lib/runtimeStatus';
import { toBackendMode } from '@/lib/agentModes';
import { useAppStore } from '@/store/useAppStore';
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

// ── NemoClaw/OpenShell policy inspection (read-only; no enforcement) ─────────────

function CapabilityRow({ label, value }: { label: string; value: boolean | null | undefined }) {
  const tone = capabilityTone(value);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <span style={{ color: 'var(--txt-2)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--txt-1)', fontWeight: 500 }}>
        <StatusDot tone={tone} />{capabilityLabel(value)}
      </span>
    </div>
  );
}

function NemoclawPolicyPanel() {
  const [result, setResult] = useState<NemoclawPolicyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.getNemoclawPolicy();   // read-only file inspection
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load policy inspection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const s = result?.summary ?? null;

  return (
    <div style={{
      marginBottom: 'var(--s3)', padding: '9px 11px', borderRadius: 'var(--r2)',
      border: '1px solid var(--line)', background: 'var(--surface-2)',
      display: 'flex', flexDirection: 'column', gap: 7,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)' }}>NemoClaw/OpenShell Policy</span>
        {result && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5,
            fontWeight: 600, color:
              policyStatusTone(result.status) === 'green' ? 'var(--green)'
              : policyStatusTone(result.status) === 'amber' ? 'var(--amber)'
              : policyStatusTone(result.status) === 'red' ? 'var(--red)' : 'var(--txt-3)',
          }}>
            <StatusDot tone={policyStatusTone(result.status)} />{policyStatusLabel(result.status)}
          </span>
        )}
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading} style={{ fontSize: 11, marginLeft: 'auto' }}>
          <Icon name="sync" size={12} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          {loading ? 'Loading…' : 'Reload inspection'}
        </button>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
        {POLICY_COPY.readOnly}
      </div>

      {error && <div style={{ fontSize: 10.5, color: 'var(--red)' }}>{error}</div>}

      {result && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10.5,
          paddingTop: 6, borderTop: '1px solid var(--line-soft)',
        }}>
          <div style={{ color: 'var(--txt-2)', lineHeight: 1.4 }}>{result.message}</div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, color: 'var(--txt-3)' }}>
            <span>Configured: {result.configured ? 'yes' : 'no'}</span>
            <span>Exists: {result.pathExists ? 'yes' : 'no'}</span>
            <span>Readable: {result.readable ? 'yes' : 'no'}</span>
            <span>Valid: {result.valid ? 'yes' : 'no'}</span>
            {result.format && <span>Format: {result.format}</span>}
          </div>
          {result.policyPathDisplay && (
            <div className="mono" style={{ color: 'var(--txt-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              path {result.policyPathDisplay}
            </div>
          )}

          {s && (
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4,
              paddingTop: 6, borderTop: '1px solid var(--line-soft)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ color: 'var(--txt-2)' }}>Declared modes</span>
                <span style={{ color: 'var(--txt-1)', fontWeight: 500 }}>
                  {s.declaredModes.length ? s.declaredModes.join(' · ') : '—'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ color: 'var(--txt-2)' }}>Network policy</span>
                <span style={{ color: 'var(--txt-1)', fontWeight: 500 }}>{s.networkPolicy ?? 'Unknown'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ color: 'var(--txt-2)' }}>Filesystem scopes</span>
                <span style={{ color: 'var(--txt-1)', fontWeight: 500 }}>
                  {s.filesystemScopes.length ? s.filesystemScopes.join(' · ') : '—'}
                </span>
              </div>
              <CapabilityRow label="Browser" value={s.browserAllowed} />
              <CapabilityRow label="Computer-use" value={s.computerUseAllowed} />
              <CapabilityRow label="MCP" value={s.mcpAllowed} />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ color: 'var(--txt-2)' }}>Credential access</span>
                <span style={{ color: 'var(--txt-1)', fontWeight: 500 }}>{s.credentialAccess}</span>
              </div>
              {s.unknownKeys.length > 0 && (
                <div style={{ color: 'var(--txt-3)', lineHeight: 1.4 }}>
                  Unknown keys: {s.unknownKeys.join(', ')}
                </div>
              )}
            </div>
          )}

          {result.warnings.length > 0 && (
            <div style={{ color: 'var(--amber)', lineHeight: 1.4, marginTop: 2 }}>
              {result.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
          {result.errors.length > 0 && (
            <div style={{ color: 'var(--red)', lineHeight: 1.4, marginTop: 2 }}>
              {result.errors.map((e, i) => <div key={i}>✕ {e}</div>)}
            </div>
          )}
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--amber)', lineHeight: 1.4 }}>
        {POLICY_COPY.disabled}
      </div>
    </div>
  );
}

// ── guardrail readiness (read-only correlation; enforces/unlocks nothing) ────────

function readinessColor(status: string): string {
  const tone = readinessStatusTone(status);
  return tone === 'green' ? 'var(--green)' : tone === 'amber' ? 'var(--amber)'
    : tone === 'red' ? 'var(--red)' : 'var(--txt-3)';
}

function ComponentChip({ label, value }: { label: string; value: string }) {
  return (
    <span style={{
      fontSize: 10, color: 'var(--txt-2)', background: 'var(--surface-1)',
      border: '1px solid var(--line)', borderRadius: 'var(--r1)', padding: '2px 6px',
    }}>
      {label}: <span style={{ color: 'var(--txt-1)', fontWeight: 500 }}>{value}</span>
    </span>
  );
}

function GuardrailReadinessPanel() {
  const [result, setResult] = useState<GuardrailReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Read-only correlation. Refreshing this NEVER triggers a health probe.
      const r = await api.getGuardrailReadiness();
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load guardrail readiness.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const c = result?.components ?? null;

  return (
    <div style={{
      marginBottom: 'var(--s3)', padding: '9px 11px', borderRadius: 'var(--r2)',
      border: '1px solid var(--line)', background: 'var(--surface-2)',
      display: 'flex', flexDirection: 'column', gap: 7,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)' }}>Guardrail Readiness</span>
        {result && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 600, color: readinessColor(result.status) }}>
            <StatusDot tone={readinessStatusTone(result.status)} />{readinessStatusLabel(result.status)}
          </span>
        )}
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading} style={{ fontSize: 11, marginLeft: 'auto' }}>
          <Icon name="sync" size={12} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          {loading ? 'Loading…' : 'Refresh readiness'}
        </button>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
        {READINESS_COPY.informational}
      </div>

      {error && <div style={{ fontSize: 10.5, color: 'var(--red)' }}>{error}</div>}

      {result && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 5, fontSize: 10.5,
          paddingTop: 6, borderTop: '1px solid var(--line-soft)',
        }}>
          <div style={{ color: 'var(--txt-2)', lineHeight: 1.45 }}>{result.summary}</div>

          {c && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 2 }}>
              <ComponentChip label="Runtime" value={c.runtimeStatus} />
              <ComponentChip label="Last probe" value={c.lastProbe} />
              <ComponentChip label="Policy" value={c.policy} />
              <ComponentChip label="Mode policy" value={c.modePolicy} />
            </div>
          )}

          {result.blockers.length > 0 && (
            <div style={{ marginTop: 2 }}>
              <div style={{ color: 'var(--txt-3)', fontWeight: 600 }}>Blockers</div>
              {result.blockers.map((b, i) => (
                <div key={i} style={{ color: 'var(--amber)', lineHeight: 1.4 }}>• {b}</div>
              ))}
            </div>
          )}

          {result.nextSteps.length > 0 && (
            <div style={{ marginTop: 2 }}>
              <div style={{ color: 'var(--txt-3)', fontWeight: 600 }}>Suggested next steps</div>
              {result.nextSteps.map((s, i) => (
                <div key={i} style={{ color: 'var(--txt-2)', lineHeight: 1.4 }}>→ {s}</div>
              ))}
            </div>
          )}

          {/* capability unlocks — explicitly all disabled */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 2 }}>
            {Object.entries(result.capabilityUnlocks).map(([k, v]) => (
              <span key={k} style={{
                fontSize: 9.5, color: 'var(--txt-3)', background: 'var(--surface-1)',
                border: '1px solid var(--line)', borderRadius: 'var(--r1)', padding: '2px 6px',
              }}>
                {k}: {v ? 'on' : 'disabled'}
              </span>
            ))}
          </div>

          {result.warnings.length > 0 && (
            <div style={{ marginTop: 2, color: 'var(--txt-3)', lineHeight: 1.4 }}>
              {result.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--amber)', lineHeight: 1.4 }}>
        {READINESS_COPY.notExecution}
      </div>
    </div>
  );
}

// ── bridge contract validator (dry-run; executes nothing) ────────────────────────

function toneColor(tone: string): string {
  return tone === 'green' ? 'var(--green)' : tone === 'amber' ? 'var(--amber)'
    : tone === 'red' ? 'var(--red)' : 'var(--txt-3)';
}

function BridgeContractValidatorPanel() {
  const agentMode = useAppStore((s) => s.agentMode);

  const [source, setSource] = useState('openclaw');
  const [actionKind, setActionKind] = useState('browser.open');
  const [reason, setReason] = useState('');
  const [argsText, setArgsText] = useState('{\n  "url": "https://example.com"\n}');
  const [result, setResult] = useState<RuntimeBridgeValidationResponse | null>(null);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const backendMode = toBackendMode(agentMode.id);

  const validate = useCallback(async () => {
    setError(null);

    // Client-side JSON validation — invalid args must NOT submit.
    let parsedArgs: Record<string, unknown> | null = null;
    const trimmed = argsText.trim();
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setError('Args must be a JSON object (e.g. { "url": "https://example.com" }).');
          return;
        }
        parsedArgs = parsed as Record<string, unknown>;
      } catch {
        setError('Args is not valid JSON. Fix it before validating.');
        return;
      }
    }

    setValidating(true);
    try {
      // Dry-run only — this never executes the action or calls a runtime.
      const r = await api.validateRuntimeBridgeRequest({
        source: source.trim() || 'openclaw',
        mode: backendMode,
        requestedAction: { kind: actionKind, args: parsedArgs },
        reason: reason.trim() || null,
      });
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed.');
    } finally {
      setValidating(false);
    }
  }, [source, backendMode, actionKind, reason, argsText]);

  const inputStyle: React.CSSProperties = {
    fontSize: 11, padding: '4px 7px', borderRadius: 'var(--r1)',
    border: '1px solid var(--line)', background: 'var(--surface-1)', color: 'var(--txt-1)', width: '100%',
  };

  return (
    <div style={{
      marginBottom: 'var(--s3)', padding: '9px 11px', borderRadius: 'var(--r2)',
      border: '1px solid var(--line)', background: 'var(--surface-2)',
      display: 'flex', flexDirection: 'column', gap: 7,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)' }}>Bridge Contract Validator</span>
        <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>· dry-run</span>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
        {BRIDGE_COPY.dryRun}
      </div>

      {/* form */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10, color: 'var(--txt-3)' }}>
          Source
          <input value={source} onChange={(e) => setSource(e.target.value)} style={inputStyle} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10, color: 'var(--txt-3)' }}>
          Mode (current)
          <input value={backendMode} readOnly disabled style={{ ...inputStyle, opacity: 0.7 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10, color: 'var(--txt-3)' }}>
          Action kind
          <select value={actionKind} onChange={(e) => setActionKind(e.target.value)} style={inputStyle}>
            {BRIDGE_ACTION_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10, color: 'var(--txt-3)' }}>
          Reason
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="why this request" style={inputStyle} />
        </label>
      </div>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10, color: 'var(--txt-3)' }}>
        Args (JSON)
        <textarea value={argsText} onChange={(e) => setArgsText(e.target.value)} rows={3}
          className="mono" style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.4 }} />
      </label>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn btn-sm btn-ghost" onClick={validate} disabled={validating} style={{ fontSize: 11 }}>
          <Icon name={validating ? 'sync' : 'shield'} size={12} style={{ animation: validating ? 'spin 1s linear infinite' : undefined }} />
          {validating ? 'Validating…' : 'Validate bridge request'}
        </button>
      </div>

      {error && <div style={{ fontSize: 10.5, color: 'var(--red)' }}>{error}</div>}

      {result && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 5, fontSize: 10.5,
          paddingTop: 6, borderTop: '1px solid var(--line-soft)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontWeight: 600, color: toneColor(bridgeStatusTone(result.status)) }}>
              <StatusDot tone={bridgeStatusTone(result.status)} />{bridgeStatusLabel(result.status)}
            </span>
            <span style={{ color: 'var(--txt-3)' }}>· {result.decision}</span>
            <span style={{ fontWeight: 600, color: toneColor(riskTone(result.riskLevel)) }}>risk: {result.riskLevel}</span>
            <span style={{ color: 'var(--txt-3)' }}>· {result.actionKind} · {result.mode}</span>
          </div>

          <div style={{ color: 'var(--txt-2)', lineHeight: 1.45 }}>{result.message}</div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, color: 'var(--txt-3)' }}>
            <span>schema: {result.checks.schemaValid ? 'ok' : 'invalid'}</span>
            <span>mode: {result.checks.modeAllowsEvaluation ? 'evaluates' : 'blocked'}</span>
            <span>guardrail: {result.checks.guardrailReadyForBridgeDesign ? 'ready' : 'not ready'}</span>
            <span>bridge: {result.checks.runtimeBridgeImplemented ? 'implemented' : 'not implemented'}</span>
            <span>gateway: {result.checks.permissionGatewayDecision}</span>
          </div>

          {/* execution posture — always off */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, color: 'var(--txt-3)' }}>
            <span>allowed: {result.allowed ? 'yes' : 'no'}</span>
            <span>requires approval: {result.requiresApproval ? 'yes' : 'no'}</span>
            <span>execution: {result.executionEnabled ? 'on' : 'disabled'}</span>
          </div>

          {result.blockers.length > 0 && (
            <div>
              <div style={{ color: 'var(--txt-3)', fontWeight: 600 }}>Blockers</div>
              {result.blockers.map((b, i) => <div key={i} style={{ color: 'var(--amber)', lineHeight: 1.4 }}>• {b}</div>)}
            </div>
          )}
          {result.warnings.length > 0 && (
            <div style={{ color: 'var(--txt-3)', lineHeight: 1.4 }}>
              {result.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
          {result.logId && (
            <div className="mono" style={{ color: 'var(--txt-3)', fontSize: 9.5 }}>log {result.logId}</div>
          )}
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--amber)', lineHeight: 1.4 }}>
        {BRIDGE_COPY.notApproval}
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

      {/* read-only correlation of runtime status + last probe + policy + mode policy */}
      <GuardrailReadinessPanel />

      {/* dry-run validator for a FUTURE bridge request — executes nothing, unlocks nothing */}
      <BridgeContractValidatorPanel />

      {/* explicit, opt-in NemoClaw/OpenShell reachability probe — unlocks nothing */}
      <NemoclawProbePanel />

      {/* read-only NemoClaw/OpenShell policy inspection — no enforcement, no unlocks */}
      <NemoclawPolicyPanel />

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

  // Readiness — one compact read-only line (refresh triggers no probe).
  const [readiness, setReadiness] = useState<GuardrailReadinessResponse | null>(null);
  useEffect(() => {
    let alive = true;
    api.getGuardrailReadiness()
      .then((r) => { if (alive) setReadiness(r); })
      .catch(() => { /* non-fatal — hide the line */ });
    return () => { alive = false; };
  }, []);

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
      {readiness && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 11, marginTop: 4 }}>
          <span style={{ color: 'var(--txt-2)' }}>Guardrail readiness</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--txt-1)', fontWeight: 500 }}>
            <StatusDot tone={readinessStatusTone(readiness.status)} />{readinessStatusLabel(readiness.status)}
          </span>
        </div>
      )}
      <div style={{
        marginTop: 'var(--s2)', paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)',
        fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.45,
      }}>
        Agent remains evaluate-only. Guardrail readiness does not enable execution. No mode executes tools from chat.
      </div>
    </div>
  );
}
