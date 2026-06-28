import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { ToolConnectionStatus, PermissionPolicy, ToolRequestEvaluationResponse, ToolExecutionResponse, PermissionEvaluationLog } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { EmptyState } from '@/components/ui/EmptyState';
import { useRuntimeStatus } from '@/lib/runtimeStatus';
import { RuntimeGuardrails } from '@/components/runtime/RuntimeStatus';

// Category display config + render order. Maps backend category ids → section labels.
const CATEGORY_ORDER: { id: string; label: string; icon: string }[] = [
  { id: 'runtime',   label: 'Agent Runtime',         icon: 'sphere' },
  { id: 'mcp',       label: 'MCP',                    icon: 'layers' },
  { id: 'browser',   label: 'Browser / Computer Use', icon: 'search' },
  { id: 'external',  label: 'External Services',      icon: 'cal'    },
  { id: 'developer', label: 'Developer Tools',        icon: 'cube'   },
];

// Status → badge styling + dot tone. Nothing here ever renders as "connected/ready"
// because the backend never reports `available` in this build.
function statusStyle(status: string): { label: string; css: React.CSSProperties; dot: 'amber' | 'green' | 'grey' | 'red' } {
  switch (status) {
    case 'available':
      return { label: 'Available', css: { color: 'var(--green)', border: '1px solid var(--green-line)', background: 'var(--green-bg)' }, dot: 'green' };
    case 'not_configured':
      return { label: 'Not configured', css: { color: 'var(--amber)', border: '1px solid var(--amber-line)', background: 'var(--amber-bg)' }, dot: 'amber' };
    case 'planned':
      return { label: 'Planned', css: { color: 'var(--txt-2)', border: '1px solid var(--line)', background: 'transparent' }, dot: 'grey' };
    case 'disabled':
      return { label: 'Disabled', css: { color: 'var(--txt-3)', border: '1px solid var(--line)', background: 'transparent' }, dot: 'grey' };
    case 'error':
      return { label: 'Error', css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red' };
    case 'unavailable':
      return { label: 'Unavailable', css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red' };
    default:
      return { label: status, css: { color: 'var(--txt-3)', border: '1px solid var(--line)', background: 'transparent' }, dot: 'grey' };
  }
}

function riskColor(risk: string): string {
  if (risk === 'high')   return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--green)';
}

// ── token list (capabilities / allowed / blocked / requires) ────────────────────

function TokenRow({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  if (!items.length) {
    return (
      <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'baseline' }}>
        <span style={{ fontSize: 10, color: 'var(--txt-3)', minWidth: 78, flexShrink: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
        <span style={{ fontSize: 11, color: 'var(--txt-3)' }}>—</span>
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'baseline' }}>
      <span style={{ fontSize: 10, color: 'var(--txt-3)', minWidth: 78, flexShrink: 0, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 3 }}>{label}</span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {items.map((t) => (
          <span
            key={t}
            className="mono"
            style={{ fontSize: 10, padding: '1px 6px', borderRadius: 'var(--r1)', color: tone, border: '1px solid var(--line-soft)', background: 'var(--surface-2)' }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── tool card ───────────────────────────────────────────────────────────────────

function ToolCard({ t }: { t: ToolConnectionStatus }) {
  const s = statusStyle(t.status);
  return (
    <div className="panel" style={{ padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      {/* header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--s3)' }}>
        <StatusDot tone={s.dot} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)' }}>{t.name}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 1 }}>{t.id}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: riskColor(t.riskLevel), textTransform: 'uppercase', letterSpacing: '0.04em' }} title="Risk level">
            {t.riskLevel} risk
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...s.css }}>
            {s.label}
          </span>
        </div>
      </div>

      {/* enabled indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--txt-2)' }}>
        <Icon name={t.enabled ? 'check' : 'x'} size={12} style={{ color: t.enabled ? 'var(--green)' : 'var(--txt-3)' }} />
        {t.enabled ? 'Enabled' : 'Disabled'}
      </div>

      {/* notes */}
      {t.notes && (
        <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5 }}>{t.notes}</div>
      )}

      {/* token rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)' }}>
        <TokenRow label="Capabilities" items={t.capabilities} tone="var(--txt-2)" />
        <TokenRow label="Allowed now"  items={t.allowedNow}   tone="var(--green)" />
        <TokenRow label="Blocked now"  items={t.blockedNow}   tone="var(--red)" />
        <TokenRow label="Requires"     items={t.requires}     tone="var(--txt-2)" />
      </div>

      {t.lastError && (
        <div style={{ fontSize: 11, color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusDot tone="red" /> {t.lastError}
        </div>
      )}

      {/* actions — privileged actions are intentionally NOT available. The only
          live action is global Refresh. A clearly-disabled control makes the
          honesty explicit. */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 'var(--s2)' }}>
        <button
          className="btn btn-sm"
          disabled
          title="Connecting/enabling privileged tools is not implemented in this build."
          style={{ opacity: 0.5, cursor: 'not-allowed' }}
        >
          Connect / Enable — Not wired yet
        </button>
      </div>
    </div>
  );
}

// ── permission gateway ──────────────────────────────────────────────────────────

function riskBadgeColor(risk: string): string {
  if (risk === 'high' || risk === 'disabled') return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--green)';
}

function policyStatusColor(status: string): string {
  if (status === 'available') return 'var(--green)';
  if (status === 'not_wired') return 'var(--amber)';
  return 'var(--txt-3)'; // disabled
}

function decisionStyle(decision: string): { css: React.CSSProperties; dot: 'amber' | 'green' | 'grey' | 'red'; label: string } {
  switch (decision) {
    case 'requires_approval':
      return { css: { color: 'var(--amber)', border: '1px solid var(--amber-line)', background: 'var(--amber-bg)' }, dot: 'amber', label: 'Requires approval' };
    case 'not_wired':
      return { css: { color: 'var(--amber)', border: '1px solid var(--line)', background: 'transparent' }, dot: 'grey', label: 'Not wired' };
    case 'disabled':
      return { css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red', label: 'Disabled' };
    case 'denied':
    default:
      return { css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red', label: 'Denied' };
  }
}

function PolicyTable({ policies }: { policies: PermissionPolicy[] }) {
  const cell: React.CSSProperties = { padding: '7px 8px', fontSize: 11.5, color: 'var(--txt-1)', borderBottom: '1px solid var(--line-soft)', verticalAlign: 'top' };
  const head: React.CSSProperties = { padding: '6px 8px', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--txt-3)', textAlign: 'left', borderBottom: '1px solid var(--line)', whiteSpace: 'nowrap' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={head}>Tool</th>
            <th style={head}>Category</th>
            <th style={head}>Risk</th>
            <th style={head}>Status</th>
            <th style={head}>Approval</th>
            <th style={head}>Execution</th>
            <th style={head}>Notes</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.tool}>
              <td style={{ ...cell }} className="mono"><span style={{ color: 'var(--txt-0)' }}>{p.tool}</span></td>
              <td style={cell}>{p.category}</td>
              <td style={{ ...cell, color: riskBadgeColor(p.riskLevel), fontWeight: 600 }}>{p.riskLevel}</td>
              <td style={{ ...cell, color: policyStatusColor(p.status), fontWeight: 600 }}>{p.status}</td>
              <td style={cell}>{p.requiresApproval ? 'Yes' : 'No'}</td>
              <td style={{ ...cell, color: 'var(--txt-3)' }}>{p.executionEnabled ? 'On' : 'Off'}</td>
              <td style={{ ...cell, color: 'var(--txt-2)', fontSize: 11, minWidth: 220 }}>{p.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultPanel({ r }: { r: ToolRequestEvaluationResponse }) {
  const d = decisionStyle(r.decision);
  const row = (label: string, value: React.ReactNode) => (
    <div style={{ display: 'flex', gap: 'var(--s2)', fontSize: 11.5 }}>
      <span style={{ color: 'var(--txt-3)', minWidth: 130, flexShrink: 0 }}>{label}</span>
      <span style={{ color: 'var(--txt-1)' }}>{value}</span>
    </div>
  );
  return (
    <div className="panel" style={{ padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', borderColor: 'var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)' }}>
        <StatusDot tone={d.dot} />
        <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)', flex: 1 }}>{r.tool}</span>
        <span style={{ fontSize: 10.5, fontWeight: 600, padding: '2px 8px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...d.css }}>
          {d.label}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)' }}>
        {row('Allowed', <span style={{ color: 'var(--red)' }}>false</span>)}
        {row('Execution enabled', <span style={{ color: 'var(--txt-3)' }}>{String(r.executionEnabled)} (v0 executes nothing)</span>)}
        {row('Risk level', <span style={{ color: riskBadgeColor(r.riskLevel), fontWeight: 600 }}>{r.riskLevel}</span>)}
        {row('Approval required', r.requiresApproval ? 'Yes' : 'No')}
        {row('Would log', String(r.wouldLog))}
        {row('Sanitized args', <span className="mono" style={{ fontSize: 11 }}>{r.sanitizedArgsSummary}</span>)}
        {row('Reason', r.reason)}
        {r.policyNotes && row('Policy notes', <span style={{ color: 'var(--txt-2)' }}>{r.policyNotes}</span>)}
      </div>
    </div>
  );
}

const LOG_DECISIONS = ['denied', 'requires_approval', 'not_wired', 'disabled'] as const;

// Only these low-risk read-only brain tools may execute through the gateway.
const EXECUTABLE_TOOLS = ['brain.status', 'brain.raw_status', 'brain.vault_path'];

function ExecResultPanel({ r }: { r: ToolExecutionResponse }) {
  const executed = r.decision === 'executed';
  const row = (label: string, value: React.ReactNode) => (
    <div style={{ display: 'flex', gap: 'var(--s2)', fontSize: 11.5 }}>
      <span style={{ color: 'var(--txt-3)', minWidth: 130, flexShrink: 0 }}>{label}</span>
      <span style={{ color: 'var(--txt-1)' }}>{value}</span>
    </div>
  );
  return (
    <div className="panel" style={{ padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', borderColor: executed ? 'var(--live-line)' : 'var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)' }}>
        <StatusDot tone={!executed ? 'grey' : r.ok ? 'green' : 'red'} />
        <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-0)', flex: 1 }}>{r.tool}</span>
        <span style={{ fontSize: 10.5, fontWeight: 600, padding: '2px 8px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em',
          color: executed ? 'var(--live)' : 'var(--txt-3)', border: `1px solid ${executed ? 'var(--live-line)' : 'var(--line)'}`, background: executed ? 'var(--live-bg)' : 'transparent' }}>
          {r.decision}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)' }}>
        {!executed && r.error && row('Result', <span style={{ color: 'var(--txt-2)' }}>{r.error}</span>)}
        {executed && row('Status', <span style={{ color: r.ok ? 'var(--green)' : 'var(--red)' }}>{r.ok ? 'success' : 'failure'}</span>)}
        {executed && row('Exit code', String(r.exitCode ?? '—'))}
        {executed && r.durationMs != null && row('Duration', `${r.durationMs} ms`)}
        {row('Evaluation log', <span className="mono" style={{ fontSize: 10.5 }}>{r.evaluationLogId}</span>)}
        {row('Execution log', <span className="mono" style={{ fontSize: 10.5 }}>{r.executionLogId ?? '—'}</span>)}
        {executed && r.stdout != null && r.stdout !== '' && (
          <div>
            <div style={{ fontSize: 10, color: 'var(--txt-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>stdout</div>
            <pre className="mono" style={{ fontSize: 10.5, color: 'var(--txt-1)', background: 'var(--bg-0)', borderRadius: 'var(--r1)', padding: '8px', margin: 0, maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{r.stdout}</pre>
          </div>
        )}
        {executed && r.stderr != null && r.stderr !== '' && (
          <div>
            <div style={{ fontSize: 10, color: 'var(--txt-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>stderr</div>
            <pre className="mono" style={{ fontSize: 10.5, color: 'var(--red)', background: 'var(--bg-0)', borderRadius: 'var(--r1)', padding: '8px', margin: 0, maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{r.stderr}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

function sourceBadge(source?: string): { label: string; css: React.CSSProperties } {
  if (source === 'gateway_execution') {
    return { label: 'execution', css: { color: 'var(--live)', border: '1px solid var(--live-line)', background: 'var(--live-bg)' } };
  }
  return { label: 'eval', css: { color: 'var(--txt-2)', border: '1px solid var(--line)', background: 'transparent' } };
}

function LogRow({ l }: { l: PermissionEvaluationLog }) {
  const d = decisionStyle(l.decision === 'executed' ? 'requires_approval' : l.decision);
  const sb = sourceBadge(l.source);
  const isExec = l.source === 'gateway_execution';
  const when = l.timestamp.slice(0, 19).replace('T', ' ');
  const resultColor = l.result === 'success' ? 'var(--green)' : l.result === 'failure' ? 'var(--red)' : 'var(--txt-2)';
  return (
    <div style={{ padding: 'var(--s3)', border: '1px solid var(--line-soft)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)' }}>
        <StatusDot tone={isExec ? (l.result === 'success' ? 'green' : 'red') : d.dot} />
        <span style={{ fontSize: 9.5, fontWeight: 600, padding: '1px 5px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...sb.css }}>{sb.label}</span>
        <span className="mono" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--txt-0)' }}>{l.tool}</span>
        <span style={{ fontSize: 10.5, fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...d.css }}>{isExec ? l.decision : d.label}</span>
        <span style={{ fontSize: 10, color: riskBadgeColor(l.riskLevel), fontWeight: 600 }}>{l.riskLevel}</span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--txt-3)' }}>{when}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s3)', fontSize: 10.5, color: 'var(--txt-2)' }}>
        <span><span style={{ color: 'var(--txt-3)' }}>by</span> {l.requestedBy || '—'}</span>
        <span><span style={{ color: 'var(--txt-3)' }}>allowed</span> <span style={{ color: l.allowed ? 'var(--green)' : 'var(--red)' }}>{String(l.allowed)}</span></span>
        <span><span style={{ color: 'var(--txt-3)' }}>result</span> <span style={{ color: resultColor }}>{l.result}</span></span>
        {isExec && <span><span style={{ color: 'var(--txt-3)' }}>exit</span> {l.exitCode ?? '—'}</span>}
        {isExec && l.durationMs != null && <span><span style={{ color: 'var(--txt-3)' }}>dur</span> {l.durationMs}ms</span>}
      </div>
      <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
        <span style={{ color: 'var(--txt-3)' }}>args</span> {l.sanitizedArgsSummary || '(no args)'}
      </div>
      {isExec && l.stdoutPreview && (
        <pre className="mono" style={{ fontSize: 10, color: 'var(--txt-1)', background: 'var(--bg-0)', borderRadius: 'var(--r1)', padding: '6px 8px', margin: 0, maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{l.stdoutPreview}</pre>
      )}
      {isExec && l.stderrPreview && (
        <pre className="mono" style={{ fontSize: 10, color: 'var(--red)', background: 'var(--bg-0)', borderRadius: 'var(--r1)', padding: '6px 8px', margin: 0, maxHeight: 80, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{l.stderrPreview}</pre>
      )}
      {l.reason && <div style={{ fontSize: 10.5, color: 'var(--txt-2)' }}><span style={{ color: 'var(--txt-3)' }}>reason</span> {l.reason}</div>}
      {l.policyNotes && <div style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{l.policyNotes}</div>}
    </div>
  );
}

function PermissionGatewaySection() {
  const [policies, setPolicies] = useState<PermissionPolicy[] | null>(null);
  const [polError, setPolError] = useState<string | null>(null);

  const toolReviewTarget = useAppStore((s) => s.toolReviewTarget);
  const setToolReviewTarget = useAppStore((s) => s.setToolReviewTarget);

  const [tool, setTool]     = useState('gmail.search');
  const [reason, setReason] = useState('');
  const [argsText, setArgsText] = useState('{\n  "query": "from:example@example.com"\n}');
  const [reviewNotice, setReviewNotice] = useState<string | null>(null);

  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult]   = useState<ToolRequestEvaluationResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // safe-local execution
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState<ToolExecutionResponse | null>(null);

  // backend-local audit log
  const [logs, setLogs]         = useState<PermissionEvaluationLog[] | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [logDecision, setLogDecision] = useState<string>('');
  const [logToolSearch, setLogToolSearch] = useState<string>('');

  const loadPolicies = useCallback(async () => {
    setPolError(null);
    try {
      const res = await api.getPermissionPolicies();
      setPolicies(res.policies);
    } catch (err) {
      setPolError(err instanceof Error ? err.message : 'Failed to load policies.');
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setLogsError(null);
    try {
      const res = await api.getPermissionLogs({
        limit: 50,
        decision: logDecision || undefined,
        tool: logToolSearch.trim() || undefined,
      });
      setLogs(res.logs);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : 'Failed to load logs.');
    }
  }, [logDecision, logToolSearch]);

  useEffect(() => { loadPolicies(); }, [loadPolicies]);
  useEffect(() => { loadLogs(); }, [loadLogs]);

  // Consume a Local Agent handoff once on mount: prefill the form only — never
  // reconstruct raw args from the sanitized summary, never auto-evaluate/execute.
  useEffect(() => {
    if (!toolReviewTarget) return;
    setTool(toolReviewTarget.tool);
    setReason(toolReviewTarget.reason ?? '');
    setArgsText('{}');                 // args are not carried across the handoff
    setResult(null);
    setExecResult(null);
    setFormError(null);
    setReviewNotice('Opened from Local Agent. Review before running.');
    setToolReviewTarget(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Parse the JSON args textarea. Returns { ok, args } or sets a clear error.
  function parseArgs(): { ok: boolean; args: Record<string, unknown> | null } {
    const raw = argsText.trim();
    if (!raw) return { ok: true, args: null };
    try {
      const parsed = JSON.parse(raw);
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        setFormError('Args must be a JSON object, e.g. { "query": "…" }.');
        return { ok: false, args: null };
      }
      return { ok: true, args: parsed as Record<string, unknown> };
    } catch {
      setFormError('Invalid JSON in args. Fix the syntax or leave it empty.');
      return { ok: false, args: null };
    }
  }

  const isExecutableTool = EXECUTABLE_TOOLS.includes(tool.trim());

  async function handleEvaluate() {
    setFormError(null);
    setResult(null);
    setExecResult(null);
    if (!tool.trim()) { setFormError('Tool name is required.'); return; }
    const { ok, args } = parseArgs();
    if (!ok) return;

    setEvaluating(true);
    try {
      const res = await api.evaluateToolRequest({ tool: tool.trim(), args, reason: reason.trim() || null, requestedBy: 'manual-ui' });
      setResult(res);
      loadLogs();   // the evaluation was recorded in the backend-local audit log
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Evaluation failed.');
    } finally {
      setEvaluating(false);
    }
  }

  async function handleExecute() {
    setFormError(null);
    setResult(null);
    setExecResult(null);
    if (!isExecutableTool) return;   // button is disabled for non-safe-local tools
    const { ok, args } = parseArgs();
    if (!ok) return;

    setExecuting(true);
    try {
      const res = await api.executePermissionTool({ tool: tool.trim(), args, reason: reason.trim() || null, requestedBy: 'manual-ui' });
      setExecResult(res);
      loadLogs();   // evaluation + execution were recorded in the audit log
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Execution failed.');
    } finally {
      setExecuting(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    background: 'var(--surface-3)', color: 'var(--txt-0)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    fontSize: 12, padding: '7px 9px', width: '100%', fontFamily: 'var(--font-ui)',
  };

  return (
    <>
      {/* tool policy table */}
      <div className="panel panel-pad">
        <PanelHeader
          icon="shield"
          title="Permission Gateway — tool policies"
          sub="deny-by-default · v0"
          right={<button className="btn btn-sm btn-ghost" onClick={loadPolicies}><Icon name="sync" size={13} /> Reload</button>}
        />
        <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, marginBottom: 'var(--s3)' }}>
          Permission Gateway v0 does not execute tools. It only classifies and explains tool requests.
          MCP, Gmail, browser, computer-use, and calendar tools are not wired yet. Dangerous actions
          remain disabled by default.
        </div>
        {polError ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
            <StatusDot tone="red" /><span style={{ flex: 1 }}>{polError}</span>
            <button className="btn btn-sm btn-ghost" onClick={loadPolicies}>Retry</button>
          </div>
        ) : policies === null ? (
          <div style={{ textAlign: 'center', padding: 'var(--s6)', color: 'var(--txt-3)', fontSize: 12 }}>Loading policies…</div>
        ) : (
          <PolicyTable policies={policies} />
        )}
      </div>

      {/* evaluator */}
      <div className="panel panel-pad">
        <PanelHeader icon="bolt" title="Evaluate a tool request" sub="read-only classification — nothing is executed" />
        {reviewNotice && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: 'var(--s3) var(--s4)', marginBottom: 'var(--s3)', borderRadius: 'var(--r2)', background: 'var(--live-bg)', border: '1px solid var(--live-line)', fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5 }}>
            <StatusDot tone="live" />
            <span style={{ flex: 1 }}>
              <strong>{reviewNotice}</strong> This request came from the Local Agent. It has not been executed.
              Only low-risk local brain status tools can run here.
            </span>
            <button className="btn btn-sm btn-ghost" onClick={() => setReviewNotice(null)}>Dismiss</button>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
            <div>
              <label style={{ fontSize: 10.5, color: 'var(--txt-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tool</label>
              <input
                list="pg-tool-list" value={tool} onChange={(e) => setTool(e.target.value)}
                placeholder="e.g. gmail.search" style={{ ...inputStyle, marginTop: 4 }} className="mono"
              />
              <datalist id="pg-tool-list">
                {(policies ?? []).map((p) => <option key={p.tool} value={p.tool} />)}
              </datalist>
            </div>
            <div>
              <label style={{ fontSize: 10.5, color: 'var(--txt-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Reason (optional)</label>
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="why this would run" style={{ ...inputStyle, marginTop: 4 }} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 10.5, color: 'var(--txt-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Args (JSON object, optional)</label>
            <textarea
              value={argsText} onChange={(e) => setArgsText(e.target.value)} rows={4} spellCheck={false}
              style={{ ...inputStyle, marginTop: 4, resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            />
          </div>

          {formError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 11.5, color: 'var(--txt-0)' }}>
              <Icon name="x" size={13} style={{ color: 'var(--red)', flexShrink: 0 }} /> {formError}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-sm" onClick={handleEvaluate} disabled={evaluating || executing}>
              <Icon name="shield" size={13} /> {evaluating ? 'Evaluating…' : 'Evaluate'}
            </button>
            <button
              className="btn btn-sm"
              onClick={handleExecute}
              disabled={!isExecutableTool || evaluating || executing}
              title={isExecutableTool ? 'Run this low-risk local brain tool through the gateway' : 'Execution disabled in this build.'}
              style={!isExecutableTool ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
            >
              <Icon name="bolt" size={13} /> {executing ? 'Running…' : 'Run safe-local tool'}
            </button>
            <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
              {isExecutableTool
                ? 'Only low-risk local brain status tools can execute through the gateway in this build.'
                : 'Execution disabled in this build. Gmail, MCP, browser, computer-use, calendar, and filesystem write tools remain disabled.'}
            </span>
          </div>

          {result && <ResultPanel r={result} />}
          {execResult && <ExecResultPanel r={execResult} />}
        </div>
      </div>

      {/* permission evaluation logs */}
      <div className="panel panel-pad">
        <PanelHeader
          icon="layers"
          title="Permission Evaluation Logs"
          sub="backend app-data · read-only"
          right={<button className="btn btn-sm btn-ghost" onClick={loadLogs}><Icon name="sync" size={13} /> Refresh</button>}
        />
        <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, marginBottom: 'var(--s3)' }}>
          Records Permission Gateway evaluations (<span className="mono">eval</span>) and safe-local
          executions (<span className="mono">execution</span>). Only low-risk local brain status tools can
          execute through the gateway in this build; Gmail, MCP, browser, computer-use, calendar, and
          filesystem write tools remain disabled. Logs are stored in backend app-data, not the vault.
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)', alignItems: 'center', marginBottom: 'var(--s3)' }}>
          <input
            type="search" placeholder="Filter by tool…" value={logToolSearch}
            onChange={(e) => setLogToolSearch(e.target.value)} className="mono"
            style={{ background: 'var(--surface-3)', color: 'var(--txt-0)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5, padding: '5px 9px', minWidth: 180 }}
          />
          <select
            value={logDecision} onChange={(e) => setLogDecision(e.target.value)}
            style={{ background: 'var(--surface-2)', color: 'var(--txt-1)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5, padding: '5px 8px' }}
          >
            <option value="">All decisions</option>
            {LOG_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        {logsError ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
            <StatusDot tone="red" /><span style={{ flex: 1 }}>{logsError}</span>
            <button className="btn btn-sm btn-ghost" onClick={loadLogs}>Retry</button>
          </div>
        ) : logs === null ? (
          <div style={{ textAlign: 'center', padding: 'var(--s6)', color: 'var(--txt-3)', fontSize: 12 }}>Loading logs…</div>
        ) : logs.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--txt-3)', padding: 'var(--s4)', textAlign: 'center' }}>
            No evaluations logged yet. Evaluate a tool request above to create an entry.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
            {logs.map((l) => <LogRow key={l.id} l={l} />)}
          </div>
        )}
      </div>
    </>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export function ToolConnectionsPage() {
  const navigate = useAppStore((s) => s.navigate);

  const [items, setItems]     = useState<ToolConnectionStatus[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  // OpenClaw / NemoClaw runtime readiness (read-only; static fallback when backend down).
  const runtime = useRuntimeStatus();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getToolConnectionStatus();
      setItems(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tool connections.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const all = items ?? [];

  // group by category, preserving the configured order; unknown categories last.
  const groups = CATEGORY_ORDER
    .map((c) => ({ ...c, tools: all.filter((t) => t.category === c.id) }))
    .filter((g) => g.tools.length > 0);
  const known = new Set(CATEGORY_ORDER.map((c) => c.id));
  const otherTools = all.filter((t) => !known.has(t.category));

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>MCP / Tool Connections</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3, maxWidth: 620, lineHeight: 1.5 }}>
            Privileged tools are not enabled yet. This page shows planned integrations and what is
            currently allowed or blocked.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-ghost" onClick={() => navigate('settings')} title="Vault path + brain.cmd configuration">
            <Icon name="gear" size={13} /> Settings
          </button>
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh status
          </button>
        </div>
      </div>

      {/* honesty banner */}
      <div style={{
        padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)',
        border: '1px solid var(--amber-line)', borderRadius: 'var(--r2)',
        fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5,
      }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          Read-only inventory. No MCP, Gmail, browser, computer-use, Google, GitHub, or Drive calls are
          made — and no tool is launched or executed. Connecting/enabling privileged tools is not
          implemented in this build.
        </span>
      </div>

      {/* runtime guardrails — read-only readiness for OpenClaw / NemoClaw / browser / computer-use / MCP */}
      <RuntimeGuardrails items={runtime.items} degraded={runtime.degraded} loading={runtime.loading} />

      {/* backend error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
        </div>
      )}

      {/* loading */}
      {loading && items === null ? (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
      ) : !error && all.length === 0 ? (
        <EmptyState icon="layers" title="No tool systems" desc="The readiness inventory returned no systems." />
      ) : (
        <>
          {groups.map((g) => (
            <div key={g.id} className="panel panel-pad">
              <PanelHeader icon={g.icon} title={g.label} sub={`${g.tools.length} system${g.tools.length === 1 ? '' : 's'}`} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                {g.tools.map((t) => <ToolCard key={t.id} t={t} />)}
              </div>
            </div>
          ))}
          {otherTools.length > 0 && (
            <div className="panel panel-pad">
              <PanelHeader icon="layers" title="Other" sub={`${otherTools.length} system${otherTools.length === 1 ? '' : 's'}`} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                {otherTools.map((t) => <ToolCard key={t.id} t={t} />)}
              </div>
            </div>
          )}
        </>
      )}

      {/* permission gateway v0 — deny-by-default classification */}
      <PermissionGatewaySection />

      {/* footer note */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only. No connect / enable / authenticate / test / launch / run action is available from this page.
      </div>
    </div>
  );
}
