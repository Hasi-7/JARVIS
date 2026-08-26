/**
 * The permission / approval audit log, as a standalone panel.
 *
 * Extracted from ToolConnectionsPage so the Tool Safety page can mount the same
 * component. PRD §31 names the Safety page as where runtime logs are available,
 * and it previously said logging was "planned but not implemented" while the
 * real log lived on a different screen entirely.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { PermissionEvaluationLog } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { PanelHeader } from '@/components/ui/PanelHeader';

export const LOG_DECISIONS = [
  'allowed', 'denied', 'requires_approval', 'not_wired', 'disabled',
  'approved', 'rejected', 'executed', 'failed',
] as const;

export function decisionStyle(decision: string): { css: React.CSSProperties; dot: 'amber' | 'green' | 'grey' | 'red'; label: string } {
  switch (decision) {
    case 'allowed':
      return { css: { color: 'var(--green)', border: '1px solid var(--green-line)', background: 'var(--green-bg)' }, dot: 'green', label: 'Allowed' };
    case 'approved':
      return { css: { color: 'var(--green)', border: '1px solid var(--green-line)', background: 'var(--green-bg)' }, dot: 'green', label: 'Approved' };
    case 'executed':
      return { css: { color: 'var(--green)', border: '1px solid var(--green-line)', background: 'var(--green-bg)' }, dot: 'green', label: 'Executed' };
    case 'rejected':
      return { css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red', label: 'Rejected' };
    case 'failed':
      return { css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' }, dot: 'red', label: 'Failed' };
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

export function riskBadgeColor(risk: string): string {
  if (risk === 'high' || risk === 'disabled') return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--green)';
}

export function sourceBadge(source?: string | null): { label: string; css: React.CSSProperties } {
  if (source === 'gateway_execution') {
    return { label: 'execution', css: { color: 'var(--live)', border: '1px solid var(--live-line)', background: 'var(--live-bg)' } };
  }
  if (source === 'approval_transition') {
    return { label: 'approval', css: { color: 'var(--amber)', border: '1px solid var(--amber-line)', background: 'var(--amber-bg)' } };
  }
  if (source === 'computer_use_action') {
    return { label: 'computer use', css: { color: 'var(--red)', border: '1px solid var(--red-line)', background: 'var(--red-bg)' } };
  }
  if (source === 'runtime_bridge_validation') {
    return { label: 'bridge dry-run', css: { color: 'var(--txt-2)', border: '1px solid var(--line)', background: 'transparent' } };
  }
  return { label: 'eval', css: { color: 'var(--txt-2)', border: '1px solid var(--line)', background: 'transparent' } };
}

export function LogRow({ l }: { l: PermissionEvaluationLog }) {
  const d = decisionStyle(l.decision);
  const sb = sourceBadge(l.source);
  const isExec = l.source === 'gateway_execution';
  const when = l.timestamp.slice(0, 19).replace('T', ' ');
  const resultColor = l.result === 'success' || l.result === 'approved'
    ? 'var(--green)'
    : l.result === 'failure' || l.result === 'rejected' ? 'var(--red)' : 'var(--txt-2)';
  return (
    <div style={{ padding: 'var(--s3)', border: '1px solid var(--line-soft)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap' }}>
        <StatusDot tone={isExec ? (l.result === 'success' ? 'green' : 'red') : d.dot} />
        <span style={{ fontSize: 9.5, fontWeight: 600, padding: '1px 5px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...sb.css }}>{sb.label}</span>
        <span className="mono" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--txt-0)' }}>{l.tool}</span>
        <span style={{ fontSize: 10.5, fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...d.css }}>{d.label}</span>
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
      {(l.approvalId || l.requestId || l.approvedBy || l.approvedAt) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px var(--s3)', fontSize: 10, color: 'var(--txt-2)' }}>
          {l.approvalId && <span>approval <span className="mono" title={l.approvalId}>{l.approvalId.slice(0, 10)}…</span></span>}
          {l.requestId && <span>request <span className="mono" title={l.requestId}>{l.requestId.slice(0, 10)}…</span></span>}
          {l.approvedBy && <span>approved by {l.approvedBy}</span>}
          {l.approvedAt && <span>approved at <span className="mono">{l.approvedAt.slice(0, 19).replace('T', ' ')}</span></span>}
        </div>
      )}
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

interface PermissionLogPanelProps {
  /** Bump to force a reload after an action elsewhere on the page. */
  refreshSignal?: number;
  limit?: number;
  /** Shown under the panel title. Defaults to the full description. */
  description?: React.ReactNode;
}

const DEFAULT_DESCRIPTION = (
  <>
    Records gateway evaluations, safe-local reads, approval transitions, approved executions,
    and every computer-use action including refusals. Entries are mirrored append-only to{' '}
    <span className="mono" style={{ fontSize: 11 }}>ops/tool-logs/</span> in the vault, so the
    audit trail stays readable from Obsidian alone.
  </>
);

export function PermissionLogPanel({ refreshSignal, limit = 50, description }: PermissionLogPanelProps) {
  const [logs, setLogs] = useState<PermissionEvaluationLog[] | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [decision, setDecision] = useState('');
  const [toolSearch, setToolSearch] = useState('');

  const loadLogs = useCallback(async () => {
    setLogsError(null);
    try {
      const res = await api.getPermissionLogs({
        limit,
        decision: decision || undefined,
        tool: toolSearch.trim() || undefined,
      });
      setLogs(res.logs);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : 'Failed to load logs.');
      setLogs([]);
    }
  }, [limit, decision, toolSearch]);

  useEffect(() => { loadLogs(); }, [loadLogs]);
  useEffect(() => { if (refreshSignal) loadLogs(); }, [refreshSignal, loadLogs]);

  return (
    <div className="panel panel-pad">
      <PanelHeader
        icon="layers"
        title="Permission / Approval Audit Logs"
        sub="evaluations · transitions · executions"
        right={<button className="btn btn-sm btn-ghost" onClick={loadLogs}><Icon name="sync" size={13} /> Refresh</button>}
      />
      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, marginBottom: 'var(--s3)' }}>
        {description ?? DEFAULT_DESCRIPTION}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)', alignItems: 'center', marginBottom: 'var(--s3)' }}>
        <input
          type="search" placeholder="Filter by tool…" value={toolSearch}
          onChange={(e) => setToolSearch(e.target.value)} className="mono"
          style={{ background: 'var(--surface-3)', color: 'var(--txt-0)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5, padding: '5px 9px', minWidth: 180 }}
        />
        <select
          value={decision} onChange={(e) => setDecision(e.target.value)}
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
          No audit entries yet. Evaluations, approval transitions, and executions appear here.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          {logs.map((l) => <LogRow key={l.id} l={l} />)}
        </div>
      )}
    </div>
  );
}
