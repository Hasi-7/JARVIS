import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { api, ApiError } from '@/lib/api';
import type {
  ToolApproval, ToolApprovalReviewFields,
  ToolApprovalTaskReviewFields, ToolApprovalCalendarReviewFields,
} from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

type Action = 'approve' | 'reject' | 'execute';

interface Confirmation {
  action: Action;
  approval: ToolApproval;
}

interface ToolApprovalQueueProps {
  compact?: boolean;
  onOpenLogs?: () => void;
  onChanged?: () => void;
}

const inputStyle: CSSProperties = {
  width: '100%', background: 'var(--surface-3)', color: 'var(--txt-0)',
  border: '1px solid var(--line)', borderRadius: 'var(--r2)',
  font: 'inherit', fontSize: 11.5, padding: '7px 9px',
};

function statusTone(status: string): 'green' | 'amber' | 'red' | 'grey' | 'live' {
  if (status === 'executed') return 'green';
  if (status === 'pending_approval' || status === 'approved') return 'amber';
  if (status === 'executing') return 'live';
  if (status === 'rejected' || status === 'failed') return 'red';
  return 'grey';
}

function statusLabel(status: string): string {
  return status.replace(/_/g, ' ');
}

function formatTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function riskColor(risk: string): string {
  if (risk === 'high') return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--green)';
}

function ShortId({ value }: { value: string | null }) {
  if (!value) return <span>—</span>;
  return <span className="mono" title={value}>{value.slice(0, 10)}…</span>;
}

function reviewFieldEntries(tool: string, fields: ToolApprovalReviewFields): [string, string | null][] {
  if (tool === 'vault.create_task') {
    const task = fields as ToolApprovalTaskReviewFields;
    return [
      ['Title', task.title], ['Status', task.status], ['Area', task.area],
      ['Priority', task.priority], ['Due', task.due], ['Source', task.source],
    ];
  }
  if (tool === 'calendar.create_candidate') {
    const calendar = fields as ToolApprovalCalendarReviewFields;
    return [
      ['Date', calendar.date], ['Time', calendar.time], ['Duration', calendar.duration],
      ['Title', calendar.title], ['Reason', calendar.reason], ['Source', calendar.source],
      ['Approved', calendar.approved],
    ];
  }
  return [];
}

function ReviewFields({ approval, compact = false }: { approval: ToolApproval; compact?: boolean }) {
  const entries = reviewFieldEntries(approval.tool, approval.reviewFields);
  return (
    <div style={{ padding: compact ? '6px 7px' : '9px 10px', background: 'var(--bg-0)', borderRadius: 'var(--r2)', border: '1px solid var(--amber-line)' }}>
      <div style={{ fontSize: 9, color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>Validated review fields · immutable</div>
      {entries.length === 0 ? (
        <div style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>No arguments required for this allowlisted brain command.</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: compact ? '72px minmax(0, 1fr)' : '110px minmax(0, 1fr)', gap: '4px 9px', fontSize: compact ? 9.5 : 10.5 }}>
          {entries.map(([label, value]) => (
            <div key={label} style={{ display: 'contents' }}>
              <span style={{ color: 'var(--txt-3)' }}>{label}</span>
              <span className="mono" style={{ color: 'var(--txt-1)', overflowWrap: 'anywhere' }}>{value || '—'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function safeDetail(error: ApiError, token: string): string {
  if (!error.detail) return `Request failed with status ${error.status}.`;
  return token && error.detail.includes(token)
    ? error.detail.split(token).join('[credential redacted]')
    : error.detail;
}

function ConfirmationDialog({ confirmation, busy, operator, setOperator, rejectReason,
  setRejectReason, onCancel, onConfirm }: {
  confirmation: Confirmation;
  busy: boolean;
  operator: string;
  setOperator: (value: string) => void;
  rejectReason: string;
  setRejectReason: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const { action, approval } = confirmation;
  const verb = action === 'execute' ? 'Execute' : action === 'reject' ? 'Reject' : 'Approve';
  return (
    <div role="presentation" style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgb(0 0 0 / 0.72)', display: 'grid', placeItems: 'center', padding: 16 }} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onCancel(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="approval-confirm-title" className="panel" style={{ width: 'min(520px, 100%)', padding: 'var(--s5)', boxShadow: 'var(--shadow-pop)', borderColor: action === 'reject' ? 'var(--red-line)' : 'var(--amber-line)' }}>
        <div id="approval-confirm-title" style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{verb} tool request?</div>
        <div style={{ fontSize: 11.5, color: 'var(--txt-2)', lineHeight: 1.5, marginBottom: 'var(--s4)' }}>
          {action === 'execute'
            ? 'This is a separate privileged execution step. Approval did not run the tool.'
            : action === 'approve'
              ? 'Approval records consent only. It will not execute the tool.'
              : 'Rejection is terminal for this approval record.'}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '92px minmax(0, 1fr)', gap: '7px 10px', padding: 'var(--s3)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5, marginBottom: 'var(--s3)' }}>
          <span style={{ color: 'var(--txt-3)' }}>Tool</span><strong className="mono">{approval.tool}</strong>
          <span style={{ color: 'var(--txt-3)' }}>Risk</span><strong style={{ color: riskColor(approval.risk), textTransform: 'uppercase' }}>{approval.risk}</strong>
        </div>
        <ReviewFields approval={approval} />
        <div style={{ marginTop: 6, fontSize: 10, color: 'var(--txt-3)' }}>These backend-validated values are immutable and cannot be edited from this queue.</div>
        {action !== 'execute' && (
          <label style={{ display: 'block', marginTop: 'var(--s3)', fontSize: 10.5, color: 'var(--txt-2)' }}>
            Operator name (optional)
            <input value={operator} maxLength={80} onChange={(e) => setOperator(e.target.value)} style={{ ...inputStyle, marginTop: 4 }} disabled={busy} />
          </label>
        )}
        {action === 'reject' && (
          <label style={{ display: 'block', marginTop: 'var(--s3)', fontSize: 10.5, color: 'var(--txt-2)' }}>
            Rejection reason (optional)
            <textarea value={rejectReason} maxLength={300} rows={3} onChange={(e) => setRejectReason(e.target.value)} style={{ ...inputStyle, marginTop: 4, resize: 'vertical' }} disabled={busy} />
          </label>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 'var(--s4)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={`btn btn-sm ${action === 'reject' ? '' : 'btn-primary'}`} onClick={onConfirm} disabled={busy} style={action === 'reject' ? { color: 'var(--red)', borderColor: 'var(--red-line)' } : undefined}>
            {busy ? `${verb}…` : `Confirm ${verb.toLowerCase()}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function ApprovalCard({ approval, compact, busy, hasToken, onAction }: {
  approval: ToolApproval;
  compact: boolean;
  busy: boolean;
  hasToken: boolean;
  onAction: (action: Action, approval: ToolApproval) => void;
}) {
  const pending = approval.status === 'pending_approval';
  const approved = approval.status === 'approved';
  const timestamps = [
    ['Created', approval.createdAt], ['Approved', approval.approvedAt], ['Rejected', approval.rejectedAt],
    ['Started', approval.executionStartedAt], ['Executed', approval.executedAt], ['Failed', approval.failedAt],
  ].filter(([, value]) => value);

  return (
    <article style={{ padding: compact ? 9 : 'var(--s4)', border: '1px solid var(--line-soft)', borderRadius: 'var(--r3)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: compact ? 7 : 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, flexWrap: 'wrap' }}>
        <StatusDot tone={statusTone(approval.status)} pulse={approval.status === 'executing'} />
        <div style={{ flex: 1, minWidth: 100 }}>
          <div className="mono" style={{ fontSize: compact ? 10.5 : 12.5, fontWeight: 700, color: 'var(--txt-0)', overflowWrap: 'anywhere' }}>{approval.tool}</div>
          <div style={{ fontSize: 9.5, color: 'var(--txt-3)', marginTop: 2 }}>{approval.mode} mode · requested by {approval.requestedBy}</div>
        </div>
        <span style={{ fontSize: 9, fontWeight: 700, color: riskColor(approval.risk), textTransform: 'uppercase' }}>{approval.risk} risk</span>
        <span style={{ fontSize: 9, fontWeight: 700, color: `var(--${statusTone(approval.status) === 'live' ? 'live' : statusTone(approval.status)})`, textTransform: 'uppercase' }}>{statusLabel(approval.status)}</span>
      </div>

      <ReviewFields approval={approval} compact={compact} />
      <div className="mono" style={{ fontSize: 9, color: 'var(--txt-3)', overflowWrap: 'anywhere' }}>Audit summary: {approval.argsSummary || '(no args)'}</div>

      {(approval.reason || approval.approvedBy || approval.rejectedBy) && (
        <div style={{ fontSize: compact ? 9.5 : 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
          {approval.reason && <div><span style={{ color: 'var(--txt-3)' }}>Reason:</span> {approval.reason}</div>}
          {approval.approvedBy && <div><span style={{ color: 'var(--txt-3)' }}>Approved by:</span> {approval.approvedBy}</div>}
          {approval.rejectedBy && <div><span style={{ color: 'var(--txt-3)' }}>Rejected by:</span> {approval.rejectedBy}</div>}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(185px, 1fr))', gap: '3px 12px', fontSize: 9.5, color: 'var(--txt-3)' }}>
        {timestamps.map(([label, value]) => <span key={label}>{label}: <span style={{ color: 'var(--txt-2)' }}>{formatTime(value)}</span></span>)}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(185px, 1fr))', gap: '3px 12px', fontSize: 9.5, color: 'var(--txt-3)' }}>
        <span>Evaluation log: <ShortId value={approval.evaluationLogId} /></span>
        <span>Transition log: <ShortId value={approval.transitionLogId} /></span>
        <span>Execution log: <ShortId value={approval.executionLogId} /></span>
      </div>

      {approval.result && (
        <div style={{ padding: '7px 9px', border: `1px solid ${approval.result.ok ? 'var(--green-line)' : 'var(--red-line)'}`, borderRadius: 'var(--r2)', fontSize: 10.5, color: 'var(--txt-1)' }}>
          <strong style={{ color: approval.result.ok ? 'var(--green)' : 'var(--red)' }}>{approval.result.ok ? 'Completed' : 'Failed'}</strong> · {approval.result.message}
          {approval.result.path && <div className="mono" style={{ fontSize: 9.5, marginTop: 3, overflowWrap: 'anywhere' }}>{approval.result.path}</div>}
          {approval.result.id && <div className="mono" style={{ fontSize: 9.5, marginTop: 3 }}>Result ID: {approval.result.id}</div>}
        </div>
      )}
      {approval.error && <div style={{ padding: '7px 9px', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)', color: 'var(--txt-1)', fontSize: 10.5 }}>{approval.error}</div>}
      {approval.auditWarning && <div style={{ padding: '7px 9px', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', borderRadius: 'var(--r2)', color: 'var(--txt-1)', fontSize: 10.5 }}>{approval.auditWarning}</div>}

      {(pending || approved) && (
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {pending && <button className="btn btn-sm btn-primary" onClick={() => onAction('approve', approval)} disabled={busy || !hasToken}>Approve</button>}
          {pending && <button className="btn btn-sm" onClick={() => onAction('reject', approval)} disabled={busy || !hasToken} style={{ color: 'var(--red)' }}>Reject</button>}
          {approved && <button className="btn btn-sm btn-primary" onClick={() => onAction('execute', approval)} disabled={busy || !hasToken}><Icon name="bolt" size={12} /> Execute</button>}
          {!hasToken && <span style={{ fontSize: 9.5, color: 'var(--amber)', alignSelf: 'center' }}>Enter the operator token to enable actions.</span>}
        </div>
      )}
    </article>
  );
}

export function ToolApprovalQueue({ compact = false, onOpenLogs, onChanged }: ToolApprovalQueueProps) {
  const [approvals, setApprovals] = useState<ToolApproval[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [token, setToken] = useState('');
  const [operator, setOperator] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async (currentToken = token) => {
    if (!currentToken) return;
    setLoading(true);
    setLoadError(null);
    try {
      const response = await api.listToolApprovals(currentToken, { limit: compact ? 10 : 50 });
      setApprovals([...response.approvals].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setToken('');
        setApprovals(null);
        setLoadError(err.status === 401
          ? 'Approval authentication is required. Re-enter the operator token.'
          : 'The operator token was rejected. Re-enter the configured token.');
      } else if (err instanceof ApiError && err.status === 503) {
        setLoadError(safeDetail(err, currentToken));
      } else {
        setLoadError('Could not load the authenticated approval queue.');
      }
    } finally {
      setLoading(false);
    }
  }, [compact, token]);

  // Credentials and authenticated queue data exist only in this component instance.
  useEffect(() => () => { setToken(''); setApprovals(null); }, []);

  function begin(action: Action, approval: ToolApproval) {
    if (!token || busyId) return;
    setActionError(null);
    setRejectReason('');
    setConfirmation({ action, approval });
  }

  async function confirmAction() {
    if (!confirmation || !token || busyId) return;
    const { action, approval } = confirmation;
    setBusyId(approval.id);
    setActionError(null);
    try {
      const actor = operator.trim() || undefined;
      const updated = action === 'approve'
        ? await api.approveToolApproval(approval.id, { approvedBy: actor }, token)
        : action === 'reject'
          ? await api.rejectToolApproval(approval.id, { rejectedBy: actor, reason: rejectReason.trim() || undefined }, token)
          : await api.executeToolApproval(approval.id, token);
      setApprovals((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? [updated]);
      setConfirmation(null);
      setRejectReason('');
      onChanged?.();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setToken('');
        setApprovals(null);
        setActionError(err.status === 401
          ? 'Approval authentication is required. Re-enter the operator token.'
          : 'The operator token was rejected. Re-enter the configured token.');
      } else {
        setActionError(err instanceof ApiError && (err.status === 503 || err.status === 409)
          ? safeDetail(err, token)
          : `Could not ${action} this request. Verify operator setup and current status.`);
        await load(token);
        onChanged?.();
      }
      setConfirmation(null);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel panel-pad" aria-label="Tool approval queue">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 'var(--s3)' }}>
        <div>
          <div className="eyebrow">Tool Approval Queue</div>
          <div style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 2 }}>newest first · explicit transitions</div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={() => load()} disabled={loading || !token} title="Load or refresh approvals">
          <Icon name="sync" size={12} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          {loading ? ' Loading' : approvals === null ? ' Load' : ' Refresh'}
        </button>
      </div>

      <div style={{ padding: compact ? 8 : 'var(--s3)', marginBottom: 'var(--s3)', background: 'var(--bg-0)', border: '1px solid var(--amber-line)', borderRadius: 'var(--r2)' }}>
        <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: 'var(--txt-1)' }}>
          Operator approval token
          <input type="password" value={token} autoComplete="off" spellCheck={false} onChange={(e) => { setToken(e.target.value); setApprovals(null); setLoadError(null); setActionError(null); }} placeholder="BRAIN_UI_APPROVAL_TOKEN" style={{ ...inputStyle, marginTop: 5 }} />
        </label>
        <div style={{ marginTop: 6, fontSize: 9.5, color: 'var(--txt-3)', lineHeight: 1.45 }}>
          Must match <span className="mono">BRAIN_UI_APPROVAL_TOKEN</span>. Kept in memory only and cleared when this queue closes. The backend kill switch <span className="mono">BRAIN_UI_PRIVILEGED_EXECUTION_ENABLED</span> must also be true. Safe-local reads use a separate gateway path and do not bypass this queue.
        </div>
      </div>

      {actionError && <div style={{ padding: '7px 9px', marginBottom: 'var(--s3)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)', color: 'var(--txt-1)', fontSize: 10.5 }}>{actionError}</div>}
      {loadError ? (
        <div style={{ padding: 'var(--s3)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)', fontSize: 11 }}>
          {loadError} <button className="btn btn-sm btn-ghost" onClick={() => load()} disabled={!token}>Retry</button>
        </div>
      ) : approvals === null ? (
        <div style={{ padding: 'var(--s4)', textAlign: 'center', color: 'var(--txt-3)', fontSize: 11 }}>{loading ? 'Loading authenticated approvals…' : 'Enter the operator token, then explicitly load the queue.'}</div>
      ) : approvals.length === 0 ? (
        <div style={{ padding: 'var(--s4)', textAlign: 'center', color: 'var(--txt-3)', fontSize: 11, fontStyle: 'italic' }}>No approval records yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? 8 : 'var(--s3)', maxHeight: compact ? 620 : undefined, overflowY: compact ? 'auto' : undefined }}>
          {approvals.map((approval) => <ApprovalCard key={approval.id} approval={approval} compact={compact} busy={busyId !== null} hasToken={Boolean(token)} onAction={begin} />)}
        </div>
      )}

      {onOpenLogs && <button className="btn btn-sm btn-ghost" onClick={onOpenLogs} style={{ marginTop: 'var(--s3)', width: '100%', justifyContent: 'center' }}>Open Tool Connections / logs <Icon name="arrow-right" size={11} /></button>}
      <div style={{ marginTop: 'var(--s3)', fontSize: 9.5, color: 'var(--txt-3)', lineHeight: 1.45 }}>
        Approval never auto-executes. Approved requests require a second confirmation. Rejected, executing, executed, and failed records are non-actionable.
      </div>

      {confirmation && <ConfirmationDialog confirmation={confirmation} busy={busyId === confirmation.approval.id} operator={operator} setOperator={setOperator} rejectReason={rejectReason} setRejectReason={setRejectReason} onCancel={() => setConfirmation(null)} onConfirm={confirmAction} />}
    </section>
  );
}
