import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { ProposalItem, ProposalListError } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

const ALL = '__all__';

const STATUS_ORDER = ['pending', 'approved', 'applied', 'skipped', 'rejected'] as const;

function statusChipStyle(status: string): React.CSSProperties {
  switch (status) {
    case 'pending':  return { color: 'var(--amber)',  border: '1px solid var(--amber-line)', background: 'var(--amber-bg)' };
    case 'approved': return { color: 'var(--live)',   border: '1px solid var(--live-line)',  background: 'var(--live-bg)' };
    case 'applied':  return { color: 'var(--green)',  border: '1px solid var(--green-line)', background: 'var(--green-bg)' };
    case 'rejected': return { color: 'var(--red)',    border: '1px solid var(--red-line)',   background: 'var(--red-bg)' };
    default:         return { color: 'var(--txt-3)',  border: '1px solid var(--line)',       background: 'transparent' }; // skipped
  }
}

function statusDot(status: string): 'amber' | 'live' | 'green' | 'grey' | 'red' {
  if (status === 'pending')  return 'amber';
  if (status === 'approved') return 'live';
  if (status === 'applied')  return 'green';
  if (status === 'rejected') return 'red';
  return 'grey';
}

function riskColor(risk: string): string {
  if (risk === 'high')   return 'var(--red)';
  if (risk === 'medium') return 'var(--amber)';
  return 'var(--txt-2)';
}

function confColor(conf: string | null): string {
  if (conf === 'High')   return 'var(--green)';
  if (conf === 'Medium') return 'var(--amber)';
  if (conf === 'Low')    return 'var(--txt-3)';
  return 'var(--txt-3)';
}

function uniq(arr: (string | null | undefined)[]): string[] {
  return [...new Set(arr.filter(Boolean) as string[])].sort();
}

// ── proposal card ──────────────────────────────────────────────────────────────

function ProposalCard({ p, onOpen }: { p: ProposalItem; onOpen: (p: ProposalItem) => void }) {
  const canOpenRawInbox     = p.actions.includes('open_raw_inbox');
  const canOpenConsolidation = p.actions.includes('open_consolidation');
  const canOpenResearch      = p.actions.includes('open_research');
  const canOpenEmailIntake   = p.actions.includes('open_email_intake');
  return (
    <div className="panel" style={{ padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--s3)' }}>
        <StatusDot tone={statusDot(p.status)} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {p.title}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 2 }}>{p.summary}</div>
        </div>
        <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 'var(--r1)', textTransform: 'uppercase', letterSpacing: '0.04em', ...statusChipStyle(p.status) }}>
          {p.status}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s4)', fontSize: 11, color: 'var(--txt-2)' }}>
        <span><span style={{ color: 'var(--txt-3)' }}>Source</span> {p.source}</span>
        <span><span style={{ color: 'var(--txt-3)' }}>Type</span> {p.type}</span>
        <span><span style={{ color: 'var(--txt-3)' }}>Risk</span> <span style={{ color: riskColor(p.riskLevel) }}>{p.riskLevel}</span></span>
        {p.confidence && (
          <span><span style={{ color: 'var(--txt-3)' }}>Confidence</span> <span style={{ color: confColor(p.confidence) }}>{p.confidence}</span></span>
        )}
      </div>

      {p.targetPath && (
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.targetPath}>
          → {p.targetPath}
        </div>
      )}

      {(p.details.domain || p.details.entity || p.details.sourceType || p.details.reason) && (
        <div style={{ fontSize: 10.5, color: 'var(--txt-3)', lineHeight: 1.5, paddingTop: 'var(--s2)', borderTop: '1px solid var(--line-soft)' }}>
          {[p.details.domain, p.details.entity, p.details.sourceType].filter(Boolean).join(' · ')}
          {p.details.reason ? <> — {p.details.reason}</> : null}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        {canOpenRawInbox && (
          <button className="btn btn-sm" onClick={() => onOpen(p)} title="Open the source workflow to review / approve / route">
            Open in Raw Inbox <Icon name="chevron" size={12} />
          </button>
        )}
        {canOpenConsolidation && (
          <button className="btn btn-sm" onClick={() => onOpen(p)} title="Open the Chat/AI Consolidation page to review / edit / save">
            Open in Consolidation <Icon name="chevron" size={12} />
          </button>
        )}
        {canOpenResearch && (
          <button className="btn btn-sm" onClick={() => onOpen(p)} title="Open the Research page to review / edit / save">
            Open in Research <Icon name="chevron" size={12} />
          </button>
        )}
        {canOpenEmailIntake && (
          <button className="btn btn-sm" onClick={() => onOpen(p)} title="Open the Email Intake page to review / edit / save">
            Open in Email Intake <Icon name="chevron" size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

// ── page ────────────────────────────────────────────────────────────────────────

export function ProposalsPage() {
  const navigate = useAppStore((s) => s.navigate);
  const setProposalTarget = useAppStore((s) => s.setProposalTarget);

  const [items,  setItems]  = useState<ProposalItem[] | null>(null);
  const [errors, setErrors] = useState<ProposalListError[]>([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const [fStatus, setFStatus] = useState<string>(ALL);
  const [fType,   setFType]   = useState<string>(ALL);
  const [fSource, setFSource] = useState<string>(ALL);
  const [fConf,   setFConf]   = useState<string>(ALL);
  const [fSearch, setFSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getProposals();
      setItems(res.proposals);
      setErrors(res.errors);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load proposals.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const all = items ?? [];

  // counts
  const total   = all.length;
  const pending = all.filter((p) => p.status === 'pending').length;
  const applied = all.filter((p) => p.status === 'applied').length;
  const closed  = all.filter((p) => p.status === 'skipped' || p.status === 'rejected').length;

  // filter options
  const typeOpts   = uniq(all.map((p) => p.type));
  const sourceOpts = uniq(all.map((p) => p.source));
  const confOpts   = uniq(all.map((p) => p.confidence));

  const filtered = all.filter((p) => {
    if (fStatus !== ALL && p.status !== fStatus) return false;
    if (fType   !== ALL && p.type   !== fType)   return false;
    if (fSource !== ALL && p.source !== fSource) return false;
    if (fConf   !== ALL && p.confidence !== fConf) return false;
    if (fSearch) {
      const q = fSearch.toLowerCase();
      const hay = [p.title, p.summary, p.targetPath, p.details.domain, p.details.entity, p.details.sourceType, p.details.reason]
        .filter(Boolean).join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  function handleOpen(p: ProposalItem) {
    // Set a deep-link target (highlight only) before navigating; the source page
    // consumes it on mount. If relatedId is missing, fall back to plain navigation.
    if (p.source === 'raw-inbox') {
      if (p.relatedId) setProposalTarget({ source: 'raw-inbox', relatedId: p.relatedId });
      navigate('inbox');
    } else if (p.source === 'chat-consolidation') {
      if (p.relatedId) setProposalTarget({ source: 'chat-consolidation', relatedId: p.relatedId });
      navigate('consolidate');
    } else if (p.source === 'research') {
      if (p.relatedId) setProposalTarget({ source: 'research', relatedId: p.relatedId });
      navigate('research');
    } else if (p.source === 'email-intake') {
      if (p.relatedId) setProposalTarget({ source: 'email-intake', relatedId: p.relatedId });
      navigate('email');
    }
  }

  const selectStyle: React.CSSProperties = {
    background: 'var(--surface-2)', color: 'var(--txt-1)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    fontSize: 11.5, padding: '4px 8px', fontFamily: 'var(--font-ui)',
  };

  const statCard = (label: string, value: number, tone: string) => (
    <div className="panel" style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', lineHeight: 1, color: tone }}>
        {loading && items === null ? '…' : value}
      </span>
      <span style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>{label}</span>
    </div>
  );

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Proposal Queue</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3 }}>
            One place to review proposed changes before they are applied.
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* v1 banner */}
      <div style={{
        padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)',
        border: '1px solid var(--line)', borderRadius: 'var(--r2)',
        fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5,
      }}>
        <Icon name="shield" size={14} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>Proposal Queue v1</strong> aggregates existing Raw Inbox proposals. Apply actions still
          happen in the source workflow — this queue is read-only. Future Research, Chat Consolidation,
          Email Intake, and Agent proposals will use this same queue.
        </span>
      </div>

      {/* backend error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
        </div>
      )}

      {/* partial source errors */}
      {!error && errors.length > 0 && (
        <div style={{ padding: '8px 14px', background: 'var(--surface-2)', border: '1px solid var(--amber)', borderRadius: 'var(--r2)', fontSize: 11, color: 'var(--txt-2)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusDot tone="amber" />
          <span>Some proposal sources could not load: {errors.map((e) => e.source).join(', ')}.</span>
        </div>
      )}

      {/* counts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--s3)' }}>
        {statCard('Total', total, 'var(--txt-0)')}
        {statCard('Pending', pending, 'var(--amber)')}
        {statCard('Applied', applied, 'var(--green)')}
        {statCard('Skipped / rejected', closed, 'var(--txt-2)')}
      </div>

      {/* filters */}
      {all.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)', alignItems: 'center', padding: 'var(--s3) var(--s4)', background: 'var(--surface)', borderRadius: 'var(--r2)', border: '1px solid var(--line)' }}>
          <input
            type="search" placeholder="Search…" value={fSearch}
            onChange={(e) => setFSearch(e.target.value)}
            style={{ ...selectStyle, minWidth: 160, background: 'var(--surface-3)' }}
          />
          <select value={fStatus} onChange={(e) => setFStatus(e.target.value)} style={selectStyle}>
            <option value={ALL}>All statuses</option>
            {STATUS_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {typeOpts.length > 1 && (
            <select value={fType} onChange={(e) => setFType(e.target.value)} style={selectStyle}>
              <option value={ALL}>All types</option>
              {typeOpts.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          )}
          {sourceOpts.length > 1 && (
            <select value={fSource} onChange={(e) => setFSource(e.target.value)} style={selectStyle}>
              <option value={ALL}>All sources</option>
              {sourceOpts.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          )}
          {confOpts.length > 0 && (
            <select value={fConf} onChange={(e) => setFConf(e.target.value)} style={selectStyle}>
              <option value={ALL}>All confidence</option>
              {confOpts.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          )}
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--txt-3)' }}>
            {filtered.length} / {all.length}
          </span>
        </div>
      )}

      {/* list */}
      {loading && items === null ? (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
      ) : all.length === 0 && !error ? (
        <EmptyState
          icon="check"
          title="No proposals found."
          desc="Raw Inbox classification proposals will appear here. Future Research, Chat Consolidation, Email Intake, and Agent proposals will use this same queue."
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon="filter" title="No matching proposals" desc="Adjust the filters or search term." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          {filtered.map((p) => (
            <ProposalCard key={p.id} p={p} onOpen={handleOpen} />
          ))}
        </div>
      )}

      {/* footer note */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only. No proposal is approved, applied, or routed from this page — use the source workflow.
      </div>
    </div>
  );
}
