import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type {
  ResearchDraft,
  ResearchDomain,
  ResearchSource,
  ResearchAssistPreview,
  CreateResearchDraftRequest,
  DraftAssistModelTier,
} from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { DraftAssistPreview as DraftAssistPreviewPanel } from '@/components/ui/DraftAssistPreview';
import { useAppStore } from '@/store/useAppStore';

const DOMAINS: ResearchDomain[] = ['project', 'course', 'business', 'personal', 'technical', 'market', 'general', 'unknown'];

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

// ── sources editor ───────────────────────────────────────────────────────────────

function SourcesEditor({ value, onChange, disabled }: {
  value: ResearchSource[]; onChange: (v: ResearchSource[]) => void; disabled?: boolean;
}) {
  function update(i: number, key: keyof ResearchSource, v: string) {
    const next = value.map((s, idx) => (idx === i ? { ...s, [key]: v || null } : s));
    onChange(next);
  }
  function add() { onChange([...value, { title: null, url: null, notes: null }]); }
  function remove(i: number) { onChange(value.filter((_, idx) => idx !== i)); }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
      <label style={labelStyle}>Sources</label>
      {value.length === 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>No sources added.</div>
      )}
      {value.map((s, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.2fr auto', gap: 'var(--s2)', alignItems: 'center' }}>
          <input value={s.title ?? ''} onChange={(e) => update(i, 'title', e.target.value)} placeholder="Title" style={{ ...fieldStyle, fontSize: 11.5 }} disabled={disabled} />
          <input value={s.url ?? ''} onChange={(e) => update(i, 'url', e.target.value)} placeholder="URL (not fetched)" style={{ ...fieldStyle, fontSize: 11.5 }} disabled={disabled} />
          <input value={s.notes ?? ''} onChange={(e) => update(i, 'notes', e.target.value)} placeholder="Notes" style={{ ...fieldStyle, fontSize: 11.5 }} disabled={disabled} />
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => remove(i)} disabled={disabled} title="Remove source">✕</button>
        </div>
      ))}
      <div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={add} disabled={disabled}>
          <Icon name="plus" size={12} /> Add source
        </button>
      </div>
    </div>
  );
}

// ── shared field set (create + edit) ───────────────────────────────────────────

interface DraftFields {
  title: string; topic: string; domain: ResearchDomain; entity: string;
  researchQuestion: string; summary: string; keyFindings: string;
  sources: ResearchSource[]; openQuestions: string; recommendedNextActions: string; rawNotes: string;
}

function emptyFields(): DraftFields {
  return {
    title: '', topic: '', domain: 'unknown', entity: '', researchQuestion: '',
    summary: '', keyFindings: '', sources: [], openQuestions: '', recommendedNextActions: '', rawNotes: '',
  };
}

function fieldsFromDraft(d: ResearchDraft): DraftFields {
  return {
    title: d.title, topic: d.topic ?? '', domain: d.domain, entity: d.entity ?? '',
    researchQuestion: d.researchQuestion ?? '', summary: d.summary,
    keyFindings: arrayToLines(d.keyFindings), sources: d.sources,
    openQuestions: arrayToLines(d.openQuestions),
    recommendedNextActions: arrayToLines(d.recommendedNextActions), rawNotes: d.rawNotes,
  };
}

function buildPayload(f: DraftFields): CreateResearchDraftRequest {
  return {
    title: f.title.trim(),
    topic: f.topic.trim() || null,
    domain: f.domain,
    entity: f.entity.trim() || null,
    researchQuestion: f.researchQuestion.trim() || null,
    summary: f.summary.trim() || null,
    keyFindings: linesToArray(f.keyFindings),
    sources: f.sources,
    openQuestions: linesToArray(f.openQuestions),
    recommendedNextActions: linesToArray(f.recommendedNextActions),
    rawNotes: f.rawNotes,
  };
}

function DraftFieldSet({ f, set, disabled }: {
  f: DraftFields; set: <K extends keyof DraftFields>(k: K, v: DraftFields[K]) => void; disabled?: boolean;
}) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Title <span style={{ color: 'var(--red)' }}>*</span></label>
          <input value={f.title} onChange={(e) => set('title', e.target.value)} placeholder="e.g. Local-first RAG storage options" style={fieldStyle} disabled={disabled} />
        </div>
        <div>
          <label style={labelStyle}>Topic (optional)</label>
          <input value={f.topic} onChange={(e) => set('topic', e.target.value)} placeholder="e.g. Vector Databases" style={fieldStyle} disabled={disabled} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Domain</label>
          <select value={f.domain} onChange={(e) => set('domain', e.target.value as ResearchDomain)} style={fieldStyle} disabled={disabled}>
            {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Entity (optional)</label>
          <input value={f.entity} onChange={(e) => set('entity', e.target.value)} placeholder="e.g. JARVIS" style={fieldStyle} disabled={disabled} />
        </div>
      </div>

      <div>
        <label style={labelStyle}>Research question (optional)</label>
        <input value={f.researchQuestion} onChange={(e) => set('researchQuestion', e.target.value)} placeholder="What question is this research answering?" style={fieldStyle} disabled={disabled} />
      </div>

      <div>
        <label style={labelStyle}>Summary (optional)</label>
        <textarea value={f.summary} onChange={(e) => set('summary', e.target.value)} style={{ ...fieldStyle, minHeight: 64, resize: 'vertical' }} disabled={disabled} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
        <div>
          <label style={labelStyle}>Key findings (one per line)</label>
          <textarea value={f.keyFindings} onChange={(e) => set('keyFindings', e.target.value)} style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={disabled} />
        </div>
        <div>
          <label style={labelStyle}>Open questions (one per line)</label>
          <textarea value={f.openQuestions} onChange={(e) => set('openQuestions', e.target.value)} style={{ ...fieldStyle, minHeight: 70, resize: 'vertical' }} disabled={disabled} />
        </div>
      </div>

      <SourcesEditor value={f.sources} onChange={(v) => set('sources', v)} disabled={disabled} />

      <div>
        <label style={labelStyle}>Recommended next actions (one per line)</label>
        <textarea value={f.recommendedNextActions} onChange={(e) => set('recommendedNextActions', e.target.value)} style={{ ...fieldStyle, minHeight: 60, resize: 'vertical' }} disabled={disabled} />
      </div>

      <div>
        <label style={labelStyle}>Raw notes</label>
        <textarea value={f.rawNotes} onChange={(e) => set('rawNotes', e.target.value)} placeholder="Paste raw research notes, snippets, and links here…" style={{ ...fieldStyle, minHeight: 120, resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 11.5 }} disabled={disabled} />
        <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
          Notes and sources are untrusted text. URLs are never fetched and instructions inside them are never followed. AI assist processes saved notes only when explicitly requested; source URLs and source details are not sent.
        </div>
      </div>
    </>
  );
}

// ── new draft form ───────────────────────────────────────────────────────────────

function NewDraftForm({ onCreated }: { onCreated: () => void }) {
  const [f, setF] = useState<DraftFields>(emptyFields);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof DraftFields>(k: K, v: DraftFields[K]) {
    setF((prev) => ({ ...prev, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!f.title.trim()) { setError('Title is required.'); return; }
    if (!f.rawNotes.trim() && !f.summary.trim() && linesToArray(f.keyFindings).length === 0) {
      setError('Add at least raw notes, a summary, or one key finding.');
      return;
    }
    setBusy(true); setError(null);
    try {
      await api.createResearchDraft(buildPayload(f));
      setF(emptyFields());
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create draft.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit} style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>New research draft</div>
      <DraftFieldSet f={f} set={set} disabled={busy} />
      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>{error}</div>
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

function EditDraftModal({ draft, onClose, onSaved }: { draft: ResearchDraft; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState<DraftFields>(() => fieldsFromDraft(draft));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelTier, setModelTier] = useState<DraftAssistModelTier>('everyday');
  const [assistPreview, setAssistPreview] = useState<ResearchAssistPreview | null>(null);
  const [assisting, setAssisting] = useState(false);
  const [assistError, setAssistError] = useState<string | null>(null);

  useEffect(() => {
    setAssistPreview(null);
    setAssistError(null);
  }, [draft.id, draft.updatedAt]);

  const formSnapshot = JSON.stringify({
    title: f.title.trim(),
    topic: f.topic.trim() || null,
    domain: f.domain,
    entity: f.entity.trim() || null,
    researchQuestion: f.researchQuestion.trim() || null,
    summary: f.summary,
    keyFindings: linesToArray(f.keyFindings),
    sources: f.sources,
    openQuestions: linesToArray(f.openQuestions),
    recommendedNextActions: linesToArray(f.recommendedNextActions),
    rawNotes: f.rawNotes,
  });
  const persistedSnapshot = JSON.stringify({
    title: draft.title,
    topic: draft.topic,
    domain: draft.domain,
    entity: draft.entity,
    researchQuestion: draft.researchQuestion,
    summary: draft.summary,
    keyFindings: draft.keyFindings,
    sources: draft.sources,
    openQuestions: draft.openQuestions,
    recommendedNextActions: draft.recommendedNextActions,
    rawNotes: draft.rawNotes,
  });
  const formMatchesDraft = formSnapshot === persistedSnapshot;
  const assistContext = `${draft.id}:${draft.updatedAt}:${formSnapshot}`;
  const assistContextRef = useRef(assistContext);
  assistContextRef.current = assistContext;

  const previewStale = assistPreview !== null && (
    assistPreview.draftUpdatedAt !== draft.updatedAt || !formMatchesDraft
  );
  const previewRows = assistPreview ? [
    { label: 'Title', value: assistPreview.suggestions.title },
    { label: 'Topic', value: assistPreview.suggestions.topic },
    { label: 'Domain', value: assistPreview.suggestions.domain },
    { label: 'Entity', value: assistPreview.suggestions.entity },
    { label: 'Research question', value: assistPreview.suggestions.researchQuestion },
    { label: 'Summary', value: assistPreview.suggestions.summary },
    { label: 'Key findings', value: assistPreview.suggestions.keyFindings },
    { label: 'Open questions', value: assistPreview.suggestions.openQuestions },
    { label: 'Next actions', value: assistPreview.suggestions.recommendedNextActions },
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
      const response = await api.assistResearchDraft(draft.id, modelTier);
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
    setF((prev) => ({
      ...prev,
      ...(s.title !== undefined ? { title: s.title } : {}),
      ...(s.topic !== undefined ? { topic: s.topic ?? '' } : {}),
      ...(s.domain !== undefined ? { domain: s.domain } : {}),
      ...(s.entity !== undefined ? { entity: s.entity ?? '' } : {}),
      ...(s.researchQuestion !== undefined ? { researchQuestion: s.researchQuestion ?? '' } : {}),
      ...(s.summary !== undefined ? { summary: s.summary } : {}),
      ...(s.keyFindings !== undefined ? { keyFindings: arrayToLines(s.keyFindings) } : {}),
      ...(s.openQuestions !== undefined ? { openQuestions: arrayToLines(s.openQuestions) } : {}),
      ...(s.recommendedNextActions !== undefined ? { recommendedNextActions: arrayToLines(s.recommendedNextActions) } : {}),
    }));
    setAssistPreview(null);
    setAssistError(null);
  }

  function set<K extends keyof DraftFields>(k: K, v: DraftFields[K]) {
    setF((prev) => ({ ...prev, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (assisting) return;
    if (!f.title.trim()) { setError('Title is required.'); return; }
    setBusy(true); setError(null);
    try {
      const p = buildPayload(f);
      await api.updateResearchDraft(draft.id, { ...p, summary: f.summary, rawNotes: f.rawNotes });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update draft.');
      setBusy(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy && !assisting) onClose(); }}>
      <form className="panel" onSubmit={submit} style={{ width: 640, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)', maxHeight: '92vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Edit research draft</div>
        <DraftFieldSet f={f} set={set} disabled={busy} />
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
  draft: ResearchDraft; onClose: () => void; onConfirm: () => void; busy: boolean; error: string | null;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="panel" style={{ width: 480, padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)', boxShadow: 'var(--shadow-pop)' }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Save this research note to the vault?</div>
        <div style={{ fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          This will create one Markdown file under <span className="mono">raw/research/</span>. It will not fetch sources, call AI, create tasks, update calendar, or modify external apps.
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

function DraftCard({ draft, onEdit, onSave, highlighted }: { draft: ResearchDraft; onEdit: () => void; onSave: () => void; highlighted?: boolean }) {
  const saved = draft.status === 'saved';
  const preview = draft.summary.split('\n')[0] || draft.keyFindings[0] || 'Manual research capture';
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
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{draft.title}</div>
          <div style={{ fontSize: 11, color: 'var(--txt-2)', marginTop: 2 }}>
            {draft.domain}{draft.topic ? ` · ${draft.topic}` : ''}{draft.entity ? ` · ${draft.entity}` : ''}
          </div>
        </div>
        <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em',
          color: saved ? 'var(--green)' : 'var(--amber)',
          border: `1px solid ${saved ? 'var(--green-line)' : 'var(--amber-line)'}`,
          background: saved ? 'var(--green-bg)' : 'var(--amber-bg)' }}>
          {draft.status}
        </span>
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, maxHeight: 60, overflow: 'hidden' }}>{preview}</div>

      <div className="mono" style={{ fontSize: 10.5, color: saved ? 'var(--green)' : 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        title={saved ? (draft.savedPath ?? '') : draft.proposedDestination}>
        {saved ? `✓ ${draft.savedPath}` : `→ ${draft.proposedDestination}`}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s4)', fontSize: 11, color: 'var(--txt-3)' }}>
        {draft.keyFindings.length > 0 && <span>{draft.keyFindings.length} finding{draft.keyFindings.length > 1 ? 's' : ''}</span>}
        {draft.sources.length     > 0 && <span>{draft.sources.length} source{draft.sources.length > 1 ? 's' : ''}</span>}
        {draft.openQuestions.length > 0 && <span>{draft.openQuestions.length} open question{draft.openQuestions.length > 1 ? 's' : ''}</span>}
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

export function ResearchPage() {
  const proposalTarget    = useAppStore((s) => s.proposalTarget);
  const setProposalTarget = useAppStore((s) => s.setProposalTarget);

  const [drafts, setDrafts]   = useState<ResearchDraft[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const [editing, setEditing]       = useState<ResearchDraft | null>(null);
  const [confirming, setConfirming] = useState<ResearchDraft | null>(null);
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
      const res = await api.listResearchDrafts();
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
    if (proposalTarget?.source === 'research' && proposalTarget.relatedId) {
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
      const res = await api.saveResearchDraft(confirming.id);
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
          <div style={{ fontSize: 18, fontWeight: 700 }}>Manual Research Capture v1</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3 }}>
            Capture research notes, links, and findings by hand, review the note, then save it into the vault.
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* v1 / automation-not-wired banner */}
      <div style={{ padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5 }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>Manual capture only.</strong> Browser research automation, web search, and computer-use are
          <strong> not wired</strong>. URLs you paste are never fetched. AI assist is opt-in and preview-only; nothing is
          written to the vault until you explicitly choose <em>Save to vault</em>.
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
          <EmptyState icon="search" title="No research drafts yet." desc="Capture a research note above and create your first draft. Unsaved drafts also appear in the Proposal Queue." />
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
        Manual capture only · no browser automation · no external web fetch · no computer-use · no MCP · no automated AI
        research · AI assist is opt-in and preview-only · a vault write happens only after you confirm <em>Save to vault</em>. Saving creates one Markdown
        note under <span className="mono">raw/research/</span> and never modifies tasks, calendar, or resume.
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
