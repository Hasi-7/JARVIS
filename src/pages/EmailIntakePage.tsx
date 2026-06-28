import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type {
  EmailIntakeDraft,
  EmailIntakeDomain,
  EmailConfidence,
  CreateEmailIntakeDraftRequest,
} from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAppStore } from '@/store/useAppStore';

const DOMAINS: EmailIntakeDomain[] = ['course', 'business', 'personal', 'unknown'];
const CONFIDENCES: EmailConfidence[] = ['High', 'Medium', 'Low'];

function linesToArray(text: string): string[] {
  return text.split('\n').map((l) => l.trim()).filter(Boolean);
}
function arrayToLines(arr: string[]): string {
  return (arr ?? []).join('\n');
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

// ── new draft form ───────────────────────────────────────────────────────────────

function NewDraftForm({ onCreated }: { onCreated: () => void }) {
  const [subject, setSubject]     = useState('');
  const [sender, setSender]       = useState('');
  const [receivedAt, setReceivedAt] = useState('');
  const [domain, setDomain]       = useState<EmailIntakeDomain>('unknown');
  const [entity, setEntity]       = useState('');
  const [confidence, setConfidence] = useState<'' | EmailConfidence>('');
  const [summary, setSummary]     = useState('');
  const [actionRequired, setActionRequired] = useState('');
  const [dueDate, setDueDate]     = useState('');
  const [taskRows, setTaskRows]   = useState('');
  const [calRows, setCalRows]     = useState('');
  const [rawEmail, setRawEmail]   = useState('');

  const [busy, setBusy]   = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setSubject(''); setSender(''); setReceivedAt(''); setDomain('unknown'); setEntity('');
    setConfidence(''); setSummary(''); setActionRequired(''); setDueDate('');
    setTaskRows(''); setCalRows(''); setRawEmail('');
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim())  { setError('Subject is required.'); return; }
    if (!rawEmail.trim()) { setError('Raw email content is required.'); return; }
    setBusy(true); setError(null);
    const payload: CreateEmailIntakeDraftRequest = {
      subject: subject.trim(),
      sender: sender.trim() || null,
      receivedAt: receivedAt.trim() || null,
      domain,
      entity: entity.trim() || null,
      summary: summary.trim() || null,
      actionRequired: actionRequired.trim() || null,
      dueDate: dueDate.trim() || null,
      confidence: confidence || null,
      rawEmail,
      proposedTaskRows: linesToArray(taskRows),
      proposedCalendarRows: linesToArray(calRows),
    };
    try {
      await api.createEmailIntakeDraft(payload);
      reset();
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create draft.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit} style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>New email intake draft</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Subject <span style={{ color: 'var(--red)' }}>*</span></label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. ESC101 midterm date announcement" style={fieldStyle} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Sender (optional)</label>
          <input value={sender} onChange={(e) => setSender(e.target.value)} placeholder="prof@uni.edu" style={fieldStyle} disabled={busy} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Received date (optional)</label>
          <input value={receivedAt} onChange={(e) => setReceivedAt(e.target.value)} placeholder="2026-06-24" style={fieldStyle} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Domain</label>
          <select value={domain} onChange={(e) => setDomain(e.target.value as EmailIntakeDomain)} style={fieldStyle} disabled={busy}>
            {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Confidence</label>
          <select value={confidence} onChange={(e) => setConfidence(e.target.value as '' | EmailConfidence)} style={fieldStyle} disabled={busy}>
            <option value="">none</option>
            {CONFIDENCES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Entity (optional)</label>
          <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="e.g. ESC101 or Acme Corp" style={fieldStyle} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Due date (optional)</label>
          <input value={dueDate} onChange={(e) => setDueDate(e.target.value)} placeholder="2026-06-27" style={fieldStyle} disabled={busy} />
        </div>
      </div>

      <div>
        <label style={labelStyle}>Raw email <span style={{ color: 'var(--red)' }}>*</span></label>
        <textarea value={rawEmail} onChange={(e) => setRawEmail(e.target.value)} placeholder="Paste the full email content here…" style={{ ...fieldStyle, minHeight: 140, resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 11.5 }} disabled={busy} />
        <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
          Email content is treated as untrusted text. No instructions inside it are followed, it is never sent to an AI, and Gmail is never contacted.
        </div>
      </div>

      <div>
        <label style={labelStyle}>Summary (optional)</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Leave blank to auto-generate a conservative preview (no AI)." style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
      </div>

      <div>
        <label style={labelStyle}>Action required (optional)</label>
        <textarea value={actionRequired} onChange={(e) => setActionRequired(e.target.value)} style={{ ...fieldStyle, minHeight: 52, resize: 'vertical' }} disabled={busy} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Proposed task rows (one per line)</label>
          <textarea value={taskRows} onChange={(e) => setTaskRows(e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Proposed calendar rows (one per line)</label>
          <textarea value={calRows} onChange={(e) => setCalRows(e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
        </div>
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: -4 }}>
        Proposed task / calendar rows are <strong>informational only</strong> in v0 — saving does not create real tasks or calendar candidates.
      </div>

      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          <Icon name="plus" size={14} />
          {busy ? 'Creating…' : 'Create draft'}
        </button>
      </div>
    </form>
  );
}

// ── edit modal ─────────────────────────────────────────────────────────────────

function EditDraftModal({ draft, onClose, onSaved }: { draft: EmailIntakeDraft; onClose: () => void; onSaved: () => void }) {
  const [subject, setSubject]     = useState(draft.subject);
  const [sender, setSender]       = useState(draft.sender ?? '');
  const [receivedAt, setReceivedAt] = useState(draft.receivedAt ?? '');
  const [domain, setDomain]       = useState<EmailIntakeDomain>(draft.domain);
  const [entity, setEntity]       = useState(draft.entity ?? '');
  const [confidence, setConfidence] = useState<'' | EmailConfidence>(draft.confidence ?? '');
  const [summary, setSummary]     = useState(draft.summary);
  const [actionRequired, setActionRequired] = useState(draft.actionRequired ?? '');
  const [dueDate, setDueDate]     = useState(draft.dueDate ?? '');
  const [taskRows, setTaskRows]   = useState(arrayToLines(draft.proposedTaskRows));
  const [calRows, setCalRows]     = useState(arrayToLines(draft.proposedCalendarRows));
  const [busy, setBusy]   = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim()) { setError('Subject is required.'); return; }
    setBusy(true); setError(null);
    try {
      await api.updateEmailIntakeDraft(draft.id, {
        subject: subject.trim(),
        sender: sender.trim() || null,
        receivedAt: receivedAt.trim() || null,
        domain,
        entity: entity.trim() || null,
        confidence: confidence || null,
        summary,
        actionRequired: actionRequired.trim() || null,
        dueDate: dueDate.trim() || null,
        proposedTaskRows: linesToArray(taskRows),
        proposedCalendarRows: linesToArray(calRows),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update draft.');
      setBusy(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <form className="panel" onSubmit={submit} style={{ width: 580, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Edit draft</div>
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          The raw email is locked after creation. Editing changes only the extracted fields and routing metadata.
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Subject <span style={{ color: 'var(--red)' }}>*</span></label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
          <div>
            <label style={labelStyle}>Sender</label>
            <input value={sender} onChange={(e) => setSender(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Received date</label>
            <input value={receivedAt} onChange={(e) => setReceivedAt(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
          <div>
            <label style={labelStyle}>Domain</label>
            <select value={domain} onChange={(e) => setDomain(e.target.value as EmailIntakeDomain)} style={fieldStyle} disabled={busy}>
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Confidence</label>
            <select value={confidence} onChange={(e) => setConfidence(e.target.value as '' | EmailConfidence)} style={fieldStyle} disabled={busy}>
              <option value="">none</option>
              {CONFIDENCES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Entity</label>
            <input value={entity} onChange={(e) => setEntity(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
          <div>
            <label style={labelStyle}>Due date</label>
            <input value={dueDate} onChange={(e) => setDueDate(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
        </div>

        <div>
          <label style={labelStyle}>Summary</label>
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} style={{ ...fieldStyle, minHeight: 80, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Action required</label>
          <textarea value={actionRequired} onChange={(e) => setActionRequired(e.target.value)} style={{ ...fieldStyle, minHeight: 52, resize: 'vertical' }} disabled={busy} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Proposed task rows (one per line)</label>
            <textarea value={taskRows} onChange={(e) => setTaskRows(e.target.value)} style={{ ...fieldStyle, minHeight: 56, resize: 'vertical' }} disabled={busy} />
          </div>
          <div>
            <label style={labelStyle}>Proposed calendar rows (one per line)</label>
            <textarea value={calRows} onChange={(e) => setCalRows(e.target.value)} style={{ ...fieldStyle, minHeight: 56, resize: 'vertical' }} disabled={busy} />
          </div>
        </div>

        {error && (
          <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>{error}</div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="btn btn-sm btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
        </div>
      </form>
    </div>
  );
}

// ── save-to-vault confirmation ───────────────────────────────────────────────────

function SaveConfirmModal({ draft, onClose, onConfirm, busy, error }: {
  draft: EmailIntakeDraft; onClose: () => void; onConfirm: () => void; busy: boolean; error: string | null;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="panel" style={{ width: 480, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Save this email summary to the vault?</div>
        <div style={{ fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          This will create one Markdown file under the proposed raw email path. It will not connect to Gmail,
          mutate email, create tasks, update calendar, or call AI.
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>→ {draft.proposedDestination}</div>
        {error && (
          <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>{error}</div>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-sm btn-primary" onClick={onConfirm} disabled={busy}>{busy ? 'Saving…' : 'Save to vault'}</button>
        </div>
      </div>
    </div>
  );
}

// ── draft card ───────────────────────────────────────────────────────────────────

function DraftCard({ draft, onEdit, onSave, highlighted }: { draft: EmailIntakeDraft; onEdit: () => void; onSave: () => void; highlighted?: boolean }) {
  const saved = draft.status === 'saved';
  return (
    <div className="panel" style={{
      padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)',
      outline: highlighted ? '1px solid var(--live-line)' : undefined,
      boxShadow: highlighted ? '0 0 0 3px var(--live-bg)' : undefined,
      transition: 'box-shadow var(--fast) var(--ease), outline-color var(--fast) var(--ease)',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--s3)' }}>
        <StatusDot tone={saved ? 'green' : 'amber'} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{draft.subject}</div>
          <div style={{ fontSize: 11, color: 'var(--txt-2)', marginTop: 2 }}>
            {draft.sender ? `${draft.sender} · ` : ''}{draft.domain}{draft.entity ? ` · ${draft.entity}` : ''}{draft.confidence ? ` · ${draft.confidence}` : ''}
          </div>
        </div>
        <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em',
          color: saved ? 'var(--green)' : 'var(--amber)',
          border: `1px solid ${saved ? 'var(--green-line)' : 'var(--amber-line)'}`,
          background: saved ? 'var(--green-bg)' : 'var(--amber-bg)' }}>
          {draft.status}
        </span>
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, maxHeight: 60, overflow: 'hidden' }}>
        {(draft.summary || draft.actionRequired || '').split('\n')[0]}
      </div>

      <div className="mono" style={{ fontSize: 10.5, color: saved ? 'var(--green)' : 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        title={saved ? (draft.savedPath ?? '') : draft.proposedDestination}>
        {saved ? `✓ ${draft.savedPath}` : `→ ${draft.proposedDestination}`}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s4)', fontSize: 11, color: 'var(--txt-3)' }}>
        {draft.actionRequired && <span>action required</span>}
        {draft.dueDate && <span>due {draft.dueDate}</span>}
        {draft.proposedTaskRows.length > 0 && <span>{draft.proposedTaskRows.length} task row{draft.proposedTaskRows.length > 1 ? 's' : ''}</span>}
        {draft.proposedCalendarRows.length > 0 && <span>{draft.proposedCalendarRows.length} calendar row{draft.proposedCalendarRows.length > 1 ? 's' : ''}</span>}
      </div>

      {!saved && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)', borderTop: '1px solid var(--line-soft)', paddingTop: 'var(--s3)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onEdit}><Icon name="edit" size={12} /> Edit</button>
          <button className="btn btn-sm btn-primary" onClick={onSave}><Icon name="enter" size={12} /> Save to vault</button>
        </div>
      )}
    </div>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────────

export function EmailIntakePage() {
  const proposalTarget    = useAppStore((s) => s.proposalTarget);
  const setProposalTarget = useAppStore((s) => s.setProposalTarget);

  const [drafts, setDrafts]   = useState<EmailIntakeDraft[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const [editing, setEditing]       = useState<EmailIntakeDraft | null>(null);
  const [confirming, setConfirming] = useState<EmailIntakeDraft | null>(null);
  const [saving, setSaving]         = useState(false);
  const [saveError, setSaveError]   = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  // deep-link from Proposal Queue: highlight the exact draft (no auto-edit/save)
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [targetNotice, setTargetNotice] = useState<string | null>(null);
  const pendingTargetRef = useRef<string | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.listEmailIntakeDrafts();
      setDrafts(res.drafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load drafts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Capture the deep-link target once on mount, then clear it from the store.
  useEffect(() => {
    if (proposalTarget?.source === 'email-intake' && proposalTarget.relatedId) {
      pendingTargetRef.current = proposalTarget.relatedId;
      setProposalTarget(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Resolve the target once drafts have loaded — selection/highlight only.
  useEffect(() => {
    const targetId = pendingTargetRef.current;
    if (!targetId || drafts === null) return;
    pendingTargetRef.current = null;
    if (drafts.some((d) => d.id === targetId)) {
      setHighlightId(targetId);
      setTargetNotice('Opened from Proposal Queue.');
    } else {
      setTargetNotice('That draft could not be found. It may have been deleted.');
    }
  }, [drafts]);

  // Scroll the highlighted card into view, then fade the highlight out.
  useEffect(() => {
    if (!highlightId) return;
    highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const t = setTimeout(() => setHighlightId(null), 4000);
    return () => clearTimeout(t);
  }, [highlightId]);

  async function confirmSave() {
    if (!confirming) return;
    setSaving(true); setSaveError(null);
    try {
      const res = await api.saveEmailIntakeDraft(confirming.id);
      setSavedNotice(`Saved to ${res.relativePath}`);
      setConfirming(null);
      await load();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save draft.');
    } finally {
      setSaving(false);
    }
  }

  const all = drafts ?? [];

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Manual Email Intake v0</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3 }}>
            Paste email content, review the extracted fields, then save one Markdown summary into the vault.
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* gmail-not-wired banner */}
      <div style={{ padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5 }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>Gmail MCP is not wired.</strong> This page uses <strong>manual paste/import only</strong> — there is no Gmail
          connection, no email search/read, and Gmail mutations (send/delete/archive/labels) are <strong>disabled</strong>.
          Nothing is written to the vault until you explicitly choose <em>Save to vault</em>. No AI is called.
        </span>
      </div>

      {savedNotice && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--green-bg)', border: '1px solid var(--green-line)', fontSize: 12 }}>
          <StatusDot tone="green" />
          <span style={{ flex: 1 }} className="mono">{savedNotice}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setSavedNotice(null)}>Dismiss</button>
        </div>
      )}

      {targetNotice && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', border: '1px solid var(--line)', fontSize: 12 }}>
          <StatusDot tone="live" />
          <span style={{ flex: 1 }}>{targetNotice}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setTargetNotice(null)}>Dismiss</button>
        </div>
      )}

      {/* new draft */}
      <NewDraftForm onCreated={load} />

      {/* drafts list */}
      <div>
        <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Drafts</div>
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12, marginBottom: 'var(--s3)' }}>
            <StatusDot tone="red" />
            <span style={{ flex: 1 }}>{error}</span>
            <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          </div>
        )}
        {loading && drafts === null ? (
          <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
        ) : all.length === 0 && !error ? (
          <EmptyState icon="inbox" title="No email intake drafts yet." desc="Paste an email above and create your first draft. Unsaved drafts also appear in the Proposal Queue." />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
            {all.map((d) => (
              <div key={d.id} ref={d.id === highlightId ? highlightRef : undefined}>
                <DraftCard draft={d} highlighted={d.id === highlightId} onEdit={() => setEditing(d)} onSave={() => { setSaveError(null); setConfirming(d); }} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* safety notice */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', lineHeight: 1.6, borderTop: '1px solid var(--line-soft)', paddingTop: 'var(--s3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <Icon name="shield" size={12} /> <strong style={{ color: 'var(--txt-2)' }}>Safety</strong>
        </div>
        Manual paste only · no Gmail connection · no send / delete / archive / label changes · no MCP · no AI summarization ·
        no email instructions are followed · a vault write happens only after you confirm <em>Save to vault</em>. Saving creates
        one Markdown file under <span className="mono">raw/quercus/emails/</span>, <span className="mono">raw/business/&lt;area&gt;/emails/</span>,
        <span className="mono"> raw/personal/email/</span>, or <span className="mono">raw/inbox/email/</span>, and never creates tasks or calendar rows.
        Proposed task / calendar rows are informational only in v0.
      </div>

      {editing && (
        <EditDraftModal draft={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
      {confirming && (
        <SaveConfirmModal draft={confirming} busy={saving} error={saveError} onClose={() => setConfirming(null)} onConfirm={confirmSave} />
      )}
    </div>
  );
}
