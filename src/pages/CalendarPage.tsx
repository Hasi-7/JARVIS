import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type {
  CalendarCandidate,
  CalendarCandidatesResponse,
  CreateCalendarCandidateRequest,
  UpdateCalendarCandidateRequest,
} from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import type {
  GoogleCalendarStatusResponse,
  CalendarReconcileResponse,
  CalendarReconcileItem,
} from '@/lib/api';

// ── Google Calendar reconciliation (READ-ONLY) ───────────────────────────────────
// Compares APPROVED vault candidates against real Google Calendar events. Reports
// only — creates, moves and deletes no event, and writes no vault file.

function ReconcileGroup({ label, items, tone }: {
  label: string; items: CalendarReconcileItem[]; tone: 'green' | 'amber' | 'red' | 'live';
}) {
  if (items.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <StatusDot tone={tone} />
        <span style={{ fontSize: 11.5, fontWeight: 600 }}>{label}</span>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{items.length}</span>
      </div>
      {items.map((it, i) => (
        <div key={`${it.candidateId ?? i}`} style={{
          padding: 'var(--s2) var(--s3)', background: 'var(--surface-2)',
          border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5,
        }}>
          <div style={{ fontWeight: 600 }}>{it.title || '(untitled)'}</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 2 }}>
            {it.date ?? '—'}{it.time ? ` ${it.time}` : ''}{it.duration ? ` · ${it.duration}` : ''}
          </div>
          {it.eventTitle && (
            <div style={{ fontSize: 11, color: 'var(--txt-1)', marginTop: 3 }}>
              Calendar event: <strong>{it.eventTitle}</strong>
              {it.htmlLink && (
                <> · <a href={it.htmlLink} target="_blank" rel="noreferrer"
                        style={{ color: 'var(--live)' }}>open</a></>
              )}
            </div>
          )}
          {it.note && (
            <div style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 3 }}>{it.note}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function GoogleCalendarReconcilePanel() {
  const [status, setStatus] = useState<GoogleCalendarStatusResponse | null>(null);
  const [result, setResult] = useState<CalendarReconcileResponse | null>(null);
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    api.googleCalendarStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  const run = async () => {
    setBusy(true); setError(null);
    try {
      setResult(await api.googleCalendarReconcile());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation failed.');
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const ready = status?.readsEnabled === true;

  return (
    <div className="panel" style={{ padding: 'var(--s4) var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StatusDot tone={ready ? 'green' : 'amber'} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>Google Calendar reconciliation</span>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
          {ready ? 'read-only · authorized' : 'read-only · not authorized'}
        </span>
        <div style={{ flex: 1 }} />
        {ready && (
          <button className="btn btn-sm btn-primary" onClick={run} disabled={busy}>
            <Icon name="sync" size={13} style={{ animation: busy ? 'spin 1s linear infinite' : undefined }} />
            Reconcile
          </button>
        )}
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <Icon name="shield" size={13} style={{ color: ready ? 'var(--green)' : 'var(--amber)', marginTop: 2, flexShrink: 0 }} />
        <span>
          {status?.message ?? 'Checking Google Calendar authorization…'}{' '}
          Comparison is <strong>read-only on both sides</strong> — no calendar event is created,
          moved or deleted, and no vault file is written. Only <strong>approved</strong> candidates
          are reconciled.
        </span>
      </div>

      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)' }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
            {result.counts.events} calendar event{result.counts.events === 1 ? '' : 's'} ·{' '}
            {result.counts.matched} matched · {result.counts.conflicting} conflicting ·{' '}
            {result.counts.missing} missing · {result.counts.unparseable} unparseable
          </div>
          {result.counts.matched + result.counts.conflicting +
           result.counts.missing + result.counts.unparseable === 0 ? (
            <div style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>
              No approved candidates to reconcile.
            </div>
          ) : (
            <>
              <ReconcileGroup label="Conflicts with an existing event" items={result.conflicting} tone="red" />
              <ReconcileGroup label="Approved but not on the calendar" items={result.missing} tone="amber" />
              <ReconcileGroup label="Already on the calendar" items={result.matched} tone="green" />
              <ReconcileGroup label="Could not be parsed" items={result.unparseable} tone="live" />
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch { return iso; }
}

function truncate(s: string, n = 60): string {
  return s.length > n ? s.slice(0, n).trimEnd() + '…' : s;
}

function nowHHMM(): string {
  return new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false });
}

// ── approved styling ──────────────────────────────────────────────────────────

function approvedStyle(v: string): { color: string; bg: string } {
  if (v === 'Yes') return { color: 'var(--green)', bg: 'var(--green-bg)' };
  return { color: 'var(--amber)', bg: 'var(--amber-bg)' };
}

function ApprovedPill({ value }: { value: string }) {
  const s = approvedStyle(value);
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px',
      borderRadius: 'var(--r-pill)', fontSize: 10.5, fontWeight: 600,
      color: s.color, background: s.bg, whiteSpace: 'nowrap',
    }}>
      {value === 'Yes' ? 'Yes' : 'No'}
    </span>
  );
}

// ── parse mode badge ──────────────────────────────────────────────────────────

function ParseModeBadge({ mode }: { mode: string }) {
  const label = mode === 'markdown-table' ? 'table' : 'preview';
  const color = mode === 'markdown-table' ? 'var(--live)' : 'var(--txt-3)';
  return (
    <span style={{
      fontSize: 10.5, fontWeight: 600, color,
      background: 'var(--surface-2)', padding: '1px 7px',
      borderRadius: 'var(--r-pill)', border: '1px solid var(--line)',
    }}>
      {label}
    </span>
  );
}

// ── command output block ──────────────────────────────────────────────────────

interface CmdResult { cmd: string; ok: boolean; out: string }

function CmdOutputBlock({ result, onDismiss }: { result: CmdResult; onDismiss: () => void }) {
  return (
    <div style={{
      borderRadius: 'var(--r2)',
      background: result.ok ? 'var(--surface-2)' : 'var(--red-bg)',
      border: `1px solid ${result.ok ? 'var(--line)' : 'var(--red-line)'}`,
      padding: 'var(--s3) var(--s4)',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--s3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusDot tone={result.ok ? 'green' : 'red'} />
          <span className="mono" style={{ fontSize: 11.5, color: 'var(--txt-1)' }}>
            brain {result.cmd}
          </span>
          <span style={{ fontSize: 11, color: result.ok ? 'var(--green)' : 'var(--red)' }}>
            {result.ok ? '· done' : '· failed'}
          </span>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={onDismiss} style={{ fontSize: 11 }}>
          Dismiss
        </button>
      </div>
      {result.out && (
        <pre style={{
          margin: 0, fontFamily: 'var(--font-mono)', fontSize: 11.5,
          color: 'var(--txt-1)', whiteSpace: 'pre-wrap',
          wordBreak: 'break-word', maxHeight: 180, overflowY: 'auto',
          lineHeight: 1.5,
        }}>
          {result.out}
        </pre>
      )}
    </div>
  );
}

// ── approve confirm modal ─────────────────────────────────────────────────────

function ApproveConfirmModal({
  candidate,
  filePath,
  loading,
  error,
  onConfirm,
  onCancel,
}: {
  candidate: CalendarCandidate;
  filePath:  string;
  loading:   boolean;
  error:     string | null;
  onConfirm: () => void;
  onCancel:  () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div className="panel" style={{
        width: 400, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s3)',
        boxShadow: 'var(--shadow-pop)',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Approve candidate?</div>

        <div style={{ fontSize: 12.5, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          {truncate(candidate.title, 72)}
        </div>

        {candidate.date && (
          <div className="mono" style={{ fontSize: 11, color: 'var(--txt-2)' }}>
            {candidate.date}{candidate.time ? ` · ${candidate.time}` : ''}
            {candidate.duration ? ` · ${candidate.duration}` : ''}
          </div>
        )}

        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
          {filePath}
        </div>

        <div style={{
          fontSize: 11, color: 'var(--txt-2)',
          padding: 'var(--s2) var(--s3)',
          background: 'var(--surface-2)', borderRadius: 'var(--r2)',
          border: '1px solid var(--line)',
        }}>
          A backup will be created before writing. Approved = Yes will be written to the file.
          No event will be created in Google Calendar automatically.
        </div>

        {error && (
          <div style={{
            fontSize: 11.5, color: 'var(--red)',
            padding: 'var(--s2) var(--s3)',
            background: 'var(--red-bg)', borderRadius: 'var(--r2)',
            border: '1px solid var(--red-line)',
          }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)', marginTop: 'var(--s1)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>Cancel</button>
          <button className="btn btn-sm btn-primary" onClick={onConfirm} disabled={loading}>
            {loading ? 'Approving…' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── edit candidate modal ──────────────────────────────────────────────────────

interface EditFormData {
  date:     string;
  time:     string;
  duration: string;
  title:    string;
  reason:   string;
  source:   string;
  approved: 'Yes' | 'No';
}

function candToForm(c: CalendarCandidate): EditFormData {
  return {
    date:     c.date     ?? '',
    time:     c.time     ?? '',
    duration: c.duration ?? '',
    title:    c.title    ?? '',
    reason:   c.reason   ?? '',
    source:   c.source   ?? '',
    approved: c.approved === 'Yes' ? 'Yes' : 'No',
  };
}

function EditCandidateModal({
  candidate,
  loading,
  error,
  onSave,
  onCancel,
}: {
  candidate: CalendarCandidate;
  loading:   boolean;
  error:     string | null;
  onSave:    (payload: UpdateCalendarCandidateRequest) => void;
  onCancel:  () => void;
}) {
  const [form, setForm] = useState<EditFormData>(() => candToForm(candidate));

  function set(field: keyof EditFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) return;
    onSave({
      date:     form.date.trim(),
      time:     form.time.trim()     || null,
      duration: form.duration.trim() || null,
      title:    form.title.trim(),
      reason:   form.reason.trim()   || null,
      source:   form.source.trim()   || null,
      approved: form.approved,
    });
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%', background: 'var(--surface-2)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    padding: '6px 9px', color: 'var(--txt-0)', fontSize: 12.5,
    fontFamily: 'var(--font-ui)', outline: 'none', boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.07em',
    display: 'block', marginBottom: 4,
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div className="panel" style={{
        width: 480, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
        maxHeight: '90vh', overflowY: 'auto',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Edit candidate</div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>

          {/* title */}
          <div>
            <label style={labelStyle}>Title <span style={{ color: 'var(--red)' }}>*</span></label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
              placeholder="Event title"
              style={fieldStyle}
              autoFocus
              required
              disabled={loading}
            />
          </div>

          {/* date + time row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
            <div>
              <label style={labelStyle}>Date</label>
              <input
                type="text"
                value={form.date}
                onChange={(e) => set('date', e.target.value)}
                placeholder="YYYY-MM-DD"
                style={{ ...fieldStyle, fontFamily: 'var(--font-mono)' }}
                disabled={loading}
              />
            </div>
            <div>
              <label style={labelStyle}>Time</label>
              <input
                type="text"
                value={form.time}
                onChange={(e) => set('time', e.target.value)}
                placeholder="HH:MM"
                style={{ ...fieldStyle, fontFamily: 'var(--font-mono)' }}
                disabled={loading}
              />
            </div>
          </div>

          {/* duration + approved row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
            <div>
              <label style={labelStyle}>Duration</label>
              <input
                type="text"
                value={form.duration}
                onChange={(e) => set('duration', e.target.value)}
                placeholder="e.g. 90m, 1h"
                style={fieldStyle}
                disabled={loading}
              />
            </div>
            <div>
              <label style={labelStyle}>Approved</label>
              <select
                value={form.approved}
                onChange={(e) => set('approved', e.target.value)}
                style={fieldStyle}
                disabled={loading}
              >
                <option value="No">No</option>
                <option value="Yes">Yes</option>
              </select>
            </div>
          </div>

          {/* reason */}
          <div>
            <label style={labelStyle}>Reason <span style={{ color: 'var(--txt-3)', fontWeight: 400 }}>(optional)</span></label>
            <input
              type="text"
              value={form.reason}
              onChange={(e) => set('reason', e.target.value)}
              placeholder="Why this event was proposed"
              style={fieldStyle}
              disabled={loading}
            />
          </div>

          {/* source */}
          <div>
            <label style={labelStyle}>Source <span style={{ color: 'var(--txt-3)', fontWeight: 400 }}>(optional)</span></label>
            <input
              type="text"
              value={form.source}
              onChange={(e) => set('source', e.target.value)}
              placeholder="e.g. brain-today, email"
              style={fieldStyle}
              disabled={loading}
            />
          </div>

          {/* backup note */}
          <div style={{
            fontSize: 11, color: 'var(--txt-2)',
            padding: 'var(--s2) var(--s3)',
            background: 'var(--surface-2)', borderRadius: 'var(--r2)',
            border: '1px solid var(--line)',
          }}>
            A backup will be created before writing. No Google Calendar event will be created automatically.
          </div>

          {/* error */}
          {error && (
            <div style={{
              fontSize: 11.5, color: 'var(--red)',
              padding: 'var(--s2) var(--s3)',
              background: 'var(--red-bg)', borderRadius: 'var(--r2)',
              border: '1px solid var(--red-line)',
            }}>
              {error}
            </div>
          )}

          {/* actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)', marginTop: 'var(--s1)' }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-sm btn-primary" disabled={loading || !form.title.trim()}>
              {loading ? 'Saving…' : 'Save'}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}

function AddCandidateModal({
  loading,
  error,
  onSave,
  onCancel,
}: {
  loading:  boolean;
  error:    string | null;
  onSave:   (payload: CreateCalendarCandidateRequest) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<EditFormData>({
    date: '',
    time: '',
    duration: '',
    title: '',
    reason: '',
    source: '',
    approved: 'No',
  });
  const [localError, setLocalError] = useState<string | null>(null);

  function set(field: keyof EditFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setLocalError(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.date.trim()) {
      setLocalError('Date is required.');
      return;
    }
    if (!form.title.trim()) {
      setLocalError('Title is required.');
      return;
    }
    onSave({
      date:     form.date.trim(),
      time:     form.time.trim()     || null,
      duration: form.duration.trim() || null,
      title:    form.title.trim(),
      reason:   form.reason.trim()   || null,
      source:   form.source.trim()   || null,
      approved: form.approved,
    });
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%', background: 'var(--surface-2)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    padding: '6px 9px', color: 'var(--txt-0)', fontSize: 12.5,
    fontFamily: 'var(--font-ui)', outline: 'none', boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.07em',
    display: 'block', marginBottom: 4,
  };

  const shownError = localError || error;

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div className="panel" style={{
        width: 480, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
        maxHeight: '90vh', overflowY: 'auto',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Add candidate</div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Title <span style={{ color: 'var(--red)' }}>*</span></label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
              placeholder="Event title"
              style={fieldStyle}
              autoFocus
              required
              disabled={loading}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
            <div>
              <label style={labelStyle}>Date <span style={{ color: 'var(--red)' }}>*</span></label>
              <input
                type="text"
                value={form.date}
                onChange={(e) => set('date', e.target.value)}
                placeholder="YYYY-MM-DD"
                style={{ ...fieldStyle, fontFamily: 'var(--font-mono)' }}
                required
                disabled={loading}
              />
            </div>
            <div>
              <label style={labelStyle}>Time</label>
              <input
                type="text"
                value={form.time}
                onChange={(e) => set('time', e.target.value)}
                placeholder="HH:MM"
                style={{ ...fieldStyle, fontFamily: 'var(--font-mono)' }}
                disabled={loading}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
            <div>
              <label style={labelStyle}>Duration</label>
              <input
                type="text"
                value={form.duration}
                onChange={(e) => set('duration', e.target.value)}
                placeholder="e.g. 90m, 1h"
                style={fieldStyle}
                disabled={loading}
              />
            </div>
            <div>
              <label style={labelStyle}>Approved</label>
              <select
                value={form.approved}
                onChange={(e) => set('approved', e.target.value)}
                style={fieldStyle}
                disabled={loading}
              >
                <option value="No">No</option>
                <option value="Yes">Yes</option>
              </select>
            </div>
          </div>

          <div>
            <label style={labelStyle}>Reason <span style={{ color: 'var(--txt-3)', fontWeight: 400 }}>(optional)</span></label>
            <input
              type="text"
              value={form.reason}
              onChange={(e) => set('reason', e.target.value)}
              placeholder="Why this event was proposed"
              style={fieldStyle}
              disabled={loading}
            />
          </div>

          <div>
            <label style={labelStyle}>Source <span style={{ color: 'var(--txt-3)', fontWeight: 400 }}>(optional)</span></label>
            <input
              type="text"
              value={form.source}
              onChange={(e) => set('source', e.target.value)}
              placeholder="manual"
              style={fieldStyle}
              disabled={loading}
            />
          </div>

          <div style={{
            fontSize: 11, color: 'var(--txt-2)',
            padding: 'var(--s2) var(--s3)',
            background: 'var(--surface-2)', borderRadius: 'var(--r2)',
            border: '1px solid var(--line)', lineHeight: 1.5,
          }}>
            This adds a candidate only. It does not create a Google Calendar event.
            <br />
            A backup will be created before writing.
          </div>

          {shownError && (
            <div style={{
              fontSize: 11.5, color: 'var(--red)',
              padding: 'var(--s2) var(--s3)',
              background: 'var(--red-bg)', borderRadius: 'var(--r2)',
              border: '1px solid var(--red-line)',
            }}>
              {shownError}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)', marginTop: 'var(--s1)' }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-sm btn-primary" disabled={loading || !form.title.trim() || !form.date.trim()}>
              {loading ? 'Adding…' : 'Add candidate'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── grid layout ───────────────────────────────────────────────────────────────

// Title/Reason/Source | Date+Time | Duration | Approved | Actions
const COLS = 'minmax(0,1fr) 130px 70px 90px 100px';

// ── candidate row ─────────────────────────────────────────────────────────────

function CandidateRow({
  candidate,
  last,
  onApprove,
  onEdit,
}: {
  candidate: CalendarCandidate;
  last:      boolean;
  onApprove: (c: CalendarCandidate) => void;
  onEdit:    (c: CalendarCandidate) => void;
}) {
  const as = approvedStyle(candidate.approved);

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COLS,
      gap: 'var(--s3)', padding: '10px var(--s5)',
      alignItems: 'center',
      borderBottom: last ? 'none' : '1px solid var(--line-soft)',
    }}>
      {/* title + reason + source */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, overflow: 'hidden', minWidth: 0 }}>
        <span style={{
          fontSize: 12.5, fontWeight: 500, color: 'var(--txt-0)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }} title={candidate.title}>
          {candidate.title}
        </span>
        {candidate.reason && (
          <span style={{
            fontSize: 11, color: 'var(--txt-2)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }} title={candidate.reason}>
            {candidate.reason}
          </span>
        )}
        {candidate.source && (
          <span className="mono" style={{
            fontSize: 10.5, color: 'var(--txt-3)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }} title={candidate.source}>
            {candidate.source}
          </span>
        )}
      </div>

      {/* date + time */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span className="mono" style={{ fontSize: 11.5, color: 'var(--txt-1)' }}>
          {candidate.date || '—'}
        </span>
        {candidate.time && (
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
            {candidate.time}
          </span>
        )}
      </div>

      {/* duration */}
      <div className="mono" style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>
        {candidate.duration ?? '—'}
      </div>

      {/* approved */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          display: 'inline-block', padding: '1px 7px',
          borderRadius: 'var(--r-pill)', fontSize: 10.5, fontWeight: 600,
          color: as.color, background: as.bg, whiteSpace: 'nowrap',
        }}>
          {candidate.approved === 'Yes' ? 'Yes' : 'No'}
        </span>
      </div>

      {/* actions */}
      <div style={{ display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
        {candidate.approved !== 'Yes' && (
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => onApprove(candidate)}
            style={{ fontSize: 10.5, color: 'var(--green)' }}
            title="Approve this candidate"
          >
            Approve
          </button>
        )}
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => onEdit(candidate)}
          style={{ fontSize: 10.5 }}
          title="Edit this candidate"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function CalendarPage() {
  const showToast        = useAppStore((s) => s.showToast);
  const addCmdEntry      = useAppStore((s) => s.addCmdEntry);

  const [data,    setData]    = useState<CalendarCandidatesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // approve state
  const [approvingCand,  setApprovingCand]  = useState<CalendarCandidate | null>(null);
  const [approveLoading, setApproveLoading] = useState(false);
  const [approveError,   setApproveError]   = useState<string | null>(null);

  // edit state
  const [editingCand,  setEditingCand]  = useState<CalendarCandidate | null>(null);
  const [editLoading,  setEditLoading]  = useState(false);
  const [editError,    setEditError]    = useState<string | null>(null);

  // create/add state
  const [creatingFile, setCreatingFile] = useState(false);
  const [createError,  setCreateError]  = useState<string | null>(null);
  const [addingOpen,   setAddingOpen]   = useState(false);
  const [addLoading,   setAddLoading]   = useState(false);
  const [addError,     setAddError]     = useState<string | null>(null);

  // command output state (local, shown inline on this page)
  const [cmdResult,  setCmdResult]  = useState<{ cmd: string; ok: boolean; out: string } | null>(null);
  const [cmdRunning, setCmdRunning] = useState(false);

  // filters
  const [search,          setSearch]          = useState('');
  const [approvedFilter,  setApprovedFilter]  = useState<'all' | 'Yes' | 'No'>('all');

  // ── load ────────────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCalendarCandidates();
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calendar candidates.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── approve ──────────────────────────────────────────────────────────────────

  async function handleApprove() {
    if (!approvingCand) return;
    setApproveLoading(true);
    setApproveError(null);
    try {
      await api.approveCalendarCandidate(approvingCand.id);
      const title = approvingCand.title;
      setApprovingCand(null);
      showToast(`"${truncate(title, 30)}" approved`);
      load();
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : 'Approve failed.');
    } finally {
      setApproveLoading(false);
    }
  }

  // ── edit ─────────────────────────────────────────────────────────────────────

  async function handleEditSave(payload: UpdateCalendarCandidateRequest) {
    if (!editingCand) return;
    setEditLoading(true);
    setEditError(null);
    try {
      await api.updateCalendarCandidate(editingCand.id, payload);
      const title = payload.title;
      setEditingCand(null);
      showToast(`"${truncate(title, 30)}" saved`);
      load();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setEditLoading(false);
    }
  }

  async function handleCreateFile() {
    setCreatingFile(true);
    setCreateError(null);
    try {
      const res = await api.createCalendarCandidatesFile();
      setData(res);
      showToast('Calendar candidates file created');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Create file failed.');
    } finally {
      setCreatingFile(false);
    }
  }

  async function handleAddSave(payload: CreateCalendarCandidateRequest) {
    setAddLoading(true);
    setAddError(null);
    try {
      await api.createCalendarCandidate(payload);
      setAddingOpen(false);
      showToast(`"${truncate(payload.title, 30)}" added`);
      load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Add candidate failed.');
    } finally {
      setAddLoading(false);
    }
  }

  // ── export / open commands ───────────────────────────────────────────────────

  async function runCmd(cmd: 'calendar-export' | 'calendar-open') {
    setCmdRunning(true);
    setCmdResult(null);
    try {
      const result = await api.runBrain(cmd);
      const rawOut = result.stdout.trim() || result.stderr.trim() || (result.ok ? 'Done.' : 'Failed.');
      setCmdResult({ cmd, ok: result.ok, out: rawOut });
      addCmdEntry({
        cmd: `brain ${cmd}`,
        ok: result.ok,
        at: nowHHMM(),
        out: rawOut.split('\n').find((line) => line.trim()) ?? rawOut,
      });
      showToast(result.ok ? `brain ${cmd} · done` : `brain ${cmd} · failed`);
    } catch (err) {
      setCmdResult({
        cmd,
        ok: false,
        out: err instanceof Error ? err.message : 'Backend not reachable.',
      });
    } finally {
      setCmdRunning(false);
    }
  }

  // ── derived data ─────────────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    if (!data?.candidates) return [];
    return data.candidates.filter((c) => {
      if (approvedFilter !== 'all' && c.approved !== approvedFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (
          !c.title.toLowerCase().includes(q) &&
          !(c.reason?.toLowerCase().includes(q)) &&
          !(c.source?.toLowerCase().includes(q)) &&
          !(c.date?.toLowerCase().includes(q)) &&
          !(c.time?.toLowerCase().includes(q))
        ) return false;
      }
      return true;
    });
  }, [data, search, approvedFilter]);

  const approvedCount = useMemo(
    () => (data?.candidates ?? []).filter((c) => c.approved === 'Yes').length,
    [data],
  );
  const pendingCount = useMemo(
    () => (data?.candidates ?? []).filter((c) => c.approved !== 'Yes').length,
    [data],
  );

  const hasFilters = !!(search || approvedFilter !== 'all');

  const clearFilters = () => { setSearch(''); setApprovedFilter('all'); };

  // ── shared input style ────────────────────────────────────────────────────────

  const inp: React.CSSProperties = {
    background: 'var(--surface-2)', border: '1px solid var(--line)',
    borderRadius: 'var(--r2)', padding: '5px 9px',
    color: 'var(--txt-0)', fontSize: 12, fontFamily: 'var(--font-ui)',
    outline: 'none',
  };

  // ── render ────────────────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <GoogleCalendarReconcilePanel />

      {/* ── header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Calendar Candidates</div>
          {data && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
                {data.path}
              </span>
              {data.exists && data.parseMode !== 'missing' && (
                <>
                  <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>·</span>
                  <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{fmtDate(data.lastModified)}</span>
                  {data.parseMode === 'markdown-table' && (
                    <>
                      <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>·</span>
                      <span style={{
                        fontSize: 11, fontWeight: 600,
                        color: 'var(--live)', background: 'var(--live-bg)',
                        padding: '1px 7px', borderRadius: 'var(--r-pill)',
                      }}>
                        {data.candidates.length} candidate{data.candidates.length === 1 ? '' : 's'}
                      </span>
                      <span style={{
                        fontSize: 11, fontWeight: 600,
                        color: 'var(--green)', background: 'var(--green-bg)',
                        padding: '1px 7px', borderRadius: 'var(--r-pill)',
                      }}>
                        {approvedCount} approved
                      </span>
                      {pendingCount > 0 && (
                        <span style={{
                          fontSize: 11, fontWeight: 600,
                          color: 'var(--amber)', background: 'var(--amber-bg)',
                          padding: '1px 7px', borderRadius: 'var(--r-pill)',
                        }}>
                          {pendingCount} pending
                        </span>
                      )}
                      <ParseModeBadge mode={data.parseMode} />
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* action buttons */}
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => { setAddError(null); setAddingOpen(true); }}
            disabled={!data?.exists || data.parseMode !== 'markdown-table'}
            title="Add a candidate row"
          >
            Add candidate
          </button>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => runCmd('calendar-export')}
            disabled={cmdRunning}
            title="Run brain calendar-export to generate .ics"
          >
            <Icon name="cal" size={12} style={{ marginRight: 4 }} />
            Export .ics
          </button>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => runCmd('calendar-open')}
            disabled={cmdRunning}
            title="Run brain calendar-open"
          >
            <Icon name="cal" size={12} style={{ marginRight: 4 }} />
            Open calendar export
          </button>
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── error banner ── */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* ── command output ── */}
      {cmdResult && (
        <CmdOutputBlock result={cmdResult} onDismiss={() => setCmdResult(null)} />
      )}

      {/* ── loading ── */}
      {loading && !data && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {/* ── missing state ── */}
      {data && (data.parseMode === 'missing' || !data.exists) && (
        <EmptyState
          icon="cal"
          title="No calendar candidates file found"
          desc="Expected ops/calendar-candidates.md."
          action={(
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--s2)' }}>
              <button className="btn btn-sm btn-primary" onClick={handleCreateFile} disabled={creatingFile}>
                {creatingFile ? 'Creating…' : 'Create calendar candidates file'}
              </button>
              {createError && (
                <div style={{
                  fontSize: 11.5, color: 'var(--red)',
                  padding: 'var(--s2) var(--s3)',
                  background: 'var(--red-bg)', borderRadius: 'var(--r2)',
                  border: '1px solid var(--red-line)', maxWidth: 360,
                }}>
                  {createError}
                </div>
              )}
            </div>
          )}
        />
      )}

      {/* ── preview-only state ── */}
      {data?.exists && data.parseMode === 'preview-only' && (
        <>
          <div style={{
            padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)',
            background: 'var(--amber-bg)', border: '1px solid var(--amber-line)',
            fontSize: 12, color: 'var(--amber)', display: 'flex', gap: 6, alignItems: 'flex-start',
          }}>
            <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
            <span>
              Calendar candidates file found, but no supported Markdown table was detected. Showing preview instead.
              <strong style={{ display: 'block', marginTop: 3 }}>
                Candidate editing unavailable for this file format.
              </strong>
            </span>
          </div>
          {data.preview && (
            <div className="panel panel-pad">
              <pre style={{
                margin: 0, fontFamily: 'var(--font-mono)', fontSize: 12,
                color: 'var(--txt-1)', lineHeight: 1.65,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                maxHeight: 520, overflowY: 'auto',
              }}>
                {data.preview}
              </pre>
            </div>
          )}
        </>
      )}

      {/* ── filters + table ── */}
      {data?.exists && data.parseMode === 'markdown-table' && data.candidates.length > 0 && (
        <>
          {/* filter bar */}
          <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search candidates…"
              style={{ ...inp, width: 200 }}
            />
            <select
              value={approvedFilter}
              onChange={(e) => setApprovedFilter(e.target.value as 'all' | 'Yes' | 'No')}
              style={{ ...inp }}
            >
              <option value="all">All approved</option>
              <option value="Yes">Approved: Yes</option>
              <option value="No">Approved: No</option>
            </select>
            {hasFilters && (
              <button className="btn btn-sm btn-ghost" onClick={clearFilters} style={{ fontSize: 11 }}>
                Clear filters
              </button>
            )}
            {hasFilters && (
              <span style={{ fontSize: 11, color: 'var(--txt-3)', marginLeft: 2 }}>
                {filtered.length} / {data.candidates.length}
              </span>
            )}
          </div>

          {/* no results */}
          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: 'var(--s6)', color: 'var(--txt-3)', fontSize: 12 }}>
              No candidates match the current filters.
            </div>
          )}

          {/* table */}
          {filtered.length > 0 && (
            <div className="panel">
              {/* column headers */}
              <div style={{
                display: 'grid', gridTemplateColumns: COLS,
                gap: 'var(--s3)', padding: '6px var(--s5)',
                borderBottom: '1px solid var(--line-soft)', alignItems: 'center',
              }}>
                {['Title / Reason', 'Date / Time', 'Duration', 'Approved', 'Actions'].map((h) => (
                  <span key={h} className="eyebrow" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{h}</span>
                ))}
              </div>

              {/* rows */}
              {filtered.map((cand, i) => (
                <CandidateRow
                  key={cand.id}
                  candidate={cand}
                  last={i === filtered.length - 1}
                  onApprove={(c) => { setApproveError(null); setApprovingCand(c); }}
                  onEdit={(c)    => { setEditError(null);    setEditingCand(c);   }}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* empty (file exists, parseable, no rows) */}
      {data?.exists && data.parseMode === 'markdown-table' && data.candidates.length === 0 && (
        <EmptyState
          icon="cal"
          title="No candidates found"
          desc={`File exists at ${data.path} but contains no parseable rows.`}
          action={(
            <button
              className="btn btn-sm btn-primary"
              onClick={() => { setAddError(null); setAddingOpen(true); }}
            >
              Add candidate
            </button>
          )}
        />
      )}

      {/* ── footer ── */}
      {data?.exists && data.parseMode === 'markdown-table' && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon name="shield" size={12} />
            Approve and edit operations create a local backup under{' '}
            <span className="mono">backend/data/backups/calendar/</span> before writing.
          </div>
          <div style={{ paddingLeft: 18 }}>
            No event is written to Google Calendar automatically. Use{' '}
            <span className="mono">Export .ics</span> → import manually.
          </div>
        </div>
      )}

      {/* ── approve modal ── */}
      {approvingCand && data && (
        <ApproveConfirmModal
          candidate={approvingCand}
          filePath={data.path}
          loading={approveLoading}
          error={approveError}
          onConfirm={handleApprove}
          onCancel={() => { if (!approveLoading) { setApprovingCand(null); setApproveError(null); } }}
        />
      )}

      {/* ── edit modal ── */}
      {editingCand && (
        <EditCandidateModal
          candidate={editingCand}
          loading={editLoading}
          error={editError}
          onSave={handleEditSave}
          onCancel={() => { if (!editLoading) { setEditingCand(null); setEditError(null); } }}
        />
      )}

      {addingOpen && (
        <AddCandidateModal
          loading={addLoading}
          error={addError}
          onSave={handleAddSave}
          onCancel={() => { if (!addLoading) { setAddingOpen(false); setAddError(null); } }}
        />
      )}

    </div>
  );
}
