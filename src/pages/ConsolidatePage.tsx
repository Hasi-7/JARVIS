import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type {
  ConsolidationDraft,
  ConsolidationSourceTool,
  ConsolidationDomain,
  ConsolidationAssistPreview,
  CreateConsolidationDraftRequest,
  DraftAssistModelTier,
} from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { DraftAssistPreview as DraftAssistPreviewPanel } from '@/components/ui/DraftAssistPreview';
import { useAppStore } from '@/store/useAppStore';

const SOURCE_TOOLS: { value: ConsolidationSourceTool; label: string }[] = [
  { value: 'chatgpt',     label: 'ChatGPT' },
  { value: 'claude',      label: 'Claude' },
  { value: 'claude-code', label: 'Claude Code' },
  { value: 'opencode',    label: 'OpenCode' },
  { value: 'other',       label: 'Other' },
];

const DOMAINS: ConsolidationDomain[] = ['project', 'course', 'business', 'research', 'personal', 'unknown'];

function toolLabel(t: string): string {
  return SOURCE_TOOLS.find((s) => s.value === t)?.label ?? t;
}

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
  const [sourceTool, setSourceTool] = useState<ConsolidationSourceTool>('chatgpt');
  const [title, setTitle]           = useState('');
  const [domain, setDomain]         = useState<ConsolidationDomain>('unknown');
  const [entity, setEntity]         = useState('');
  const [transcript, setTranscript] = useState('');
  const [summary, setSummary]       = useState('');
  const [decisions, setDecisions]   = useState('');
  const [actionItems, setActionItems] = useState('');
  const [codeRefs, setCodeRefs]     = useState('');

  const [busy, setBusy]   = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setTitle(''); setEntity(''); setTranscript(''); setSummary('');
    setDecisions(''); setActionItems(''); setCodeRefs('');
    setDomain('unknown'); setSourceTool('chatgpt');
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim())      { setError('Conversation title is required.'); return; }
    if (!transcript.trim()) { setError('Transcript is required.'); return; }
    setBusy(true); setError(null);
    const payload: CreateConsolidationDraftRequest = {
      sourceTool,
      conversationTitle: title.trim(),
      domain,
      entity: entity.trim() || null,
      transcript,
      summary: summary.trim() || null,
      decisions: linesToArray(decisions),
      actionItems: linesToArray(actionItems),
      codeOrFilesReferenced: linesToArray(codeRefs),
    };
    try {
      await api.createConsolidationDraft(payload);
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
      <div style={{ fontSize: 13, fontWeight: 600 }}>New consolidation draft</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Source tool</label>
          <select value={sourceTool} onChange={(e) => setSourceTool(e.target.value as ConsolidationSourceTool)} style={fieldStyle} disabled={busy}>
            {SOURCE_TOOLS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Domain</label>
          <select value={domain} onChange={(e) => setDomain(e.target.value as ConsolidationDomain)} style={fieldStyle} disabled={busy}>
            {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Conversation title <span style={{ color: 'var(--red)' }}>*</span></label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Brain UI consolidation design" style={fieldStyle} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Entity (optional)</label>
          <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="e.g. JARVIS" style={fieldStyle} disabled={busy} />
        </div>
      </div>

      <div>
        <label style={labelStyle}>Transcript <span style={{ color: 'var(--red)' }}>*</span></label>
        <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} placeholder="Paste the full ChatGPT / Claude / Claude Code / OpenCode transcript here…" style={{ ...fieldStyle, minHeight: 140, resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 11.5 }} disabled={busy} />
        <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
          The transcript is untrusted text and its instructions are never followed. AI assist processes it only when explicitly requested from an unsaved draft.
        </div>
      </div>

      <div>
        <label style={labelStyle}>Summary (optional)</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Leave blank to auto-generate a conservative preview (no AI)." style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={busy} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Decisions (one per line)</label>
          <textarea value={decisions} onChange={(e) => setDecisions(e.target.value)} style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Action items (one per line)</label>
          <textarea value={actionItems} onChange={(e) => setActionItems(e.target.value)} style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Code / files referenced (one per line)</label>
          <textarea value={codeRefs} onChange={(e) => setCodeRefs(e.target.value)} style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={busy} />
        </div>
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

function EditDraftModal({ draft, onClose, onSaved }: { draft: ConsolidationDraft; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle]       = useState(draft.conversationTitle);
  const [domain, setDomain]     = useState<ConsolidationDomain>(draft.domain);
  const [entity, setEntity]     = useState(draft.entity ?? '');
  const [summary, setSummary]   = useState(draft.summary);
  const [decisions, setDecisions]     = useState(arrayToLines(draft.decisions));
  const [actionItems, setActionItems] = useState(arrayToLines(draft.actionItems));
  const [codeRefs, setCodeRefs]       = useState(arrayToLines(draft.codeOrFilesReferenced));
  const [busy, setBusy]   = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelTier, setModelTier] = useState<DraftAssistModelTier>('everyday');
  const [assistPreview, setAssistPreview] = useState<ConsolidationAssistPreview | null>(null);
  const [assisting, setAssisting] = useState(false);
  const [assistError, setAssistError] = useState<string | null>(null);

  useEffect(() => {
    setAssistPreview(null);
    setAssistError(null);
  }, [draft.id, draft.updatedAt]);

  const formSnapshot = JSON.stringify({
    conversationTitle: title.trim(),
    domain,
    entity: entity.trim() || null,
    summary,
    decisions: linesToArray(decisions),
    actionItems: linesToArray(actionItems),
    codeOrFilesReferenced: linesToArray(codeRefs),
  });
  const persistedSnapshot = JSON.stringify({
    conversationTitle: draft.conversationTitle,
    domain: draft.domain,
    entity: draft.entity,
    summary: draft.summary,
    decisions: draft.decisions,
    actionItems: draft.actionItems,
    codeOrFilesReferenced: draft.codeOrFilesReferenced,
  });
  const formMatchesDraft = formSnapshot === persistedSnapshot;
  const assistContext = `${draft.id}:${draft.updatedAt}:${formSnapshot}`;
  const assistContextRef = useRef(assistContext);
  assistContextRef.current = assistContext;

  const previewStale = assistPreview !== null && (
    assistPreview.draftUpdatedAt !== draft.updatedAt || !formMatchesDraft
  );
  const previewRows = assistPreview ? [
    { label: 'Conversation title', value: assistPreview.suggestions.conversationTitle },
    { label: 'Domain', value: assistPreview.suggestions.domain },
    { label: 'Entity', value: assistPreview.suggestions.entity },
    { label: 'Summary', value: assistPreview.suggestions.summary },
    { label: 'Decisions', value: assistPreview.suggestions.decisions },
    { label: 'Action items', value: assistPreview.suggestions.actionItems },
    { label: 'Code / files', value: assistPreview.suggestions.codeOrFilesReferenced },
  ].filter((row) => row.value !== undefined) : [];

  async function requestAssist() {
    if (!formMatchesDraft) {
      setAssistPreview(null);
      setAssistError('Save changes before requesting AI assist.');
      return;
    }
    const requestContext = assistContext;
    setAssisting(true); setAssistError(null); setAssistPreview(null);
    try {
      const response = await api.assistConsolidationDraft(draft.id, modelTier);
      if (assistContextRef.current !== requestContext || response.draftUpdatedAt !== draft.updatedAt) {
        setAssistError('The draft or form changed while AI assist was running. Save changes, then request a new preview.');
        return;
      }
      setAssistPreview(response);
    } catch (err) {
      setAssistError(err instanceof Error ? err.message : 'Failed to generate AI assist preview.');
    } finally {
      setAssisting(false);
    }
  }

  function applyAssistPreview() {
    if (!assistPreview || assistPreview.draftUpdatedAt !== draft.updatedAt || !formMatchesDraft) return;
    const s = assistPreview.suggestions;
    if (s.conversationTitle !== undefined) setTitle(s.conversationTitle);
    if (s.domain !== undefined) setDomain(s.domain);
    if (s.entity !== undefined) setEntity(s.entity ?? '');
    if (s.summary !== undefined) setSummary(s.summary);
    if (s.decisions !== undefined) setDecisions(arrayToLines(s.decisions));
    if (s.actionItems !== undefined) setActionItems(arrayToLines(s.actionItems));
    if (s.codeOrFilesReferenced !== undefined) setCodeRefs(arrayToLines(s.codeOrFilesReferenced));
    setAssistPreview(null);
    setAssistError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (assisting) return;
    if (!title.trim()) { setError('Conversation title is required.'); return; }
    setBusy(true); setError(null);
    try {
      await api.updateConsolidationDraft(draft.id, {
        conversationTitle: title.trim(),
        domain,
        entity: entity.trim() || null,
        summary,
        decisions: linesToArray(decisions),
        actionItems: linesToArray(actionItems),
        codeOrFilesReferenced: linesToArray(codeRefs),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update draft.');
      setBusy(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy && !assisting) onClose(); }}>
      <form className="panel" onSubmit={submit} style={{ width: 560, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Edit draft</div>
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          Source tool and transcript are locked after creation. Editing changes only the summary fields and routing metadata.
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Conversation title <span style={{ color: 'var(--red)' }}>*</span></label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} style={fieldStyle} disabled={busy} />
          </div>
          <div>
            <label style={labelStyle}>Domain</label>
            <select value={domain} onChange={(e) => setDomain(e.target.value as ConsolidationDomain)} style={fieldStyle} disabled={busy}>
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label style={labelStyle}>Entity (optional)</label>
          <input value={entity} onChange={(e) => setEntity(e.target.value)} style={fieldStyle} disabled={busy} />
        </div>

        <div>
          <label style={labelStyle}>Summary</label>
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} style={{ ...fieldStyle, minHeight: 90, resize: 'vertical' }} disabled={busy} />
        </div>

        <div>
          <label style={labelStyle}>Decisions (one per line)</label>
          <textarea value={decisions} onChange={(e) => setDecisions(e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Action items (one per line)</label>
          <textarea value={actionItems} onChange={(e) => setActionItems(e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
        </div>
        <div>
          <label style={labelStyle}>Code / files referenced (one per line)</label>
          <textarea value={codeRefs} onChange={(e) => setCodeRefs(e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={busy} />
        </div>

        <DraftAssistPreviewPanel
          modelTier={modelTier}
          onModelTierChange={(tier) => { setModelTier(tier); setAssistPreview(null); setAssistError(null); }}
          onRequest={requestAssist}
          requesting={assisting}
          disabled={busy || draft.status === 'saved'}
          preview={assistPreview}
          rows={previewRows}
          stale={previewStale}
          error={assistError}
          onApply={applyAssistPreview}
          onDismiss={() => { setAssistPreview(null); setAssistError(null); }}
        />

        {error && (
          <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>{error}</div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose} disabled={busy || assisting}>Cancel</button>
          <button type="submit" className="btn btn-sm btn-primary" disabled={busy || assisting}>{busy ? 'Saving…' : 'Save changes'}</button>
        </div>
      </form>
    </div>
  );
}

// ── save-to-vault confirmation ───────────────────────────────────────────────────

function SaveConfirmModal({ draft, onClose, onConfirm, busy, error }: {
  draft: ConsolidationDraft; onClose: () => void; onConfirm: () => void; busy: boolean; error: string | null;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="panel" style={{ width: 460, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Save this consolidation summary to the vault?</div>
        <div style={{ fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          This will create one Markdown file under <span className="mono">{`raw/chats/${draft.sourceTool}/`}</span>. It will not modify tasks, calendar, resume, or any external app.
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

function DraftCard({ draft, onEdit, onSave, highlighted }: { draft: ConsolidationDraft; onEdit: () => void; onSave: () => void; highlighted?: boolean }) {
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
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{draft.conversationTitle}</div>
          <div style={{ fontSize: 11, color: 'var(--txt-2)', marginTop: 2 }}>
            {toolLabel(draft.sourceTool)} · {draft.domain}{draft.entity ? ` · ${draft.entity}` : ''}
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
        {draft.summary.split('\n')[0]}
      </div>

      <div className="mono" style={{ fontSize: 10.5, color: saved ? 'var(--green)' : 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        title={saved ? (draft.savedPath ?? '') : draft.proposedDestination}>
        {saved ? `✓ ${draft.savedPath}` : `→ ${draft.proposedDestination}`}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s4)', fontSize: 11, color: 'var(--txt-3)' }}>
        {draft.decisions.length   > 0 && <span>{draft.decisions.length} decision{draft.decisions.length > 1 ? 's' : ''}</span>}
        {draft.actionItems.length > 0 && <span>{draft.actionItems.length} action item{draft.actionItems.length > 1 ? 's' : ''}</span>}
        {draft.codeOrFilesReferenced.length > 0 && <span>{draft.codeOrFilesReferenced.length} code/file ref{draft.codeOrFilesReferenced.length > 1 ? 's' : ''}</span>}
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

export function ConsolidatePage() {
  const proposalTarget    = useAppStore((s) => s.proposalTarget);
  const setProposalTarget = useAppStore((s) => s.setProposalTarget);

  const [drafts, setDrafts]   = useState<ConsolidationDraft[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const [editing, setEditing]       = useState<ConsolidationDraft | null>(null);
  const [confirming, setConfirming] = useState<ConsolidationDraft | null>(null);
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
      const res = await api.listConsolidationDrafts();
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
    if (proposalTarget?.source === 'chat-consolidation' && proposalTarget.relatedId) {
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
      const res = await api.saveConsolidationDraft(confirming.id);
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
          <div style={{ fontSize: 18, fontWeight: 700 }}>Manual Chat/AI Consolidation v1</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3 }}>
            Paste a ChatGPT / Claude / Claude Code / OpenCode transcript, review the summary, then save it into the vault.
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* v1 / capture-not-wired banner */}
      <div style={{ padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5 }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>Manual paste/import only.</strong> Automatic capture from ChatGPT/Claude (browser automation) and
          computer-use capture are <strong>not wired</strong>. Nothing is written to the vault until you explicitly
          choose <em>Save to vault</em>. AI assist is opt-in and preview-only; transcript instructions are never followed.
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
          <EmptyState icon="merge" title="No consolidation drafts yet." desc="Paste a transcript above and create your first draft. Unsaved drafts also appear in the Proposal Queue." />
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
        Manual paste only · no browser automation · no computer-use · no external app capture · AI assist is opt-in and
        preview-only · no transcript instructions are followed · a vault write happens only after you confirm <em>Save to vault</em>. Saving creates
        one Markdown file under <span className="mono">raw/chats/&lt;source&gt;/</span> and never modifies tasks, calendar, or resume.
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
