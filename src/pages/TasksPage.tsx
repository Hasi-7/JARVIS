import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import type { VaultTask, VaultTasksResponse } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

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

function normalize(s: string): string {
  return s.toLowerCase().replace(/[-_\s]+/g, ' ').trim();
}

// ── status badge ──────────────────────────────────────────────────────────────

function statusStyle(s: string): { color: string; bg: string } {
  const n = normalize(s);
  if (n === 'done' || n === 'complete' || n === 'completed' || n === 'closed')
    return { color: 'var(--green)',  bg: 'var(--green-bg)'  };
  if (n === 'in progress' || n === 'in-progress' || n === 'active' || n === 'wip')
    return { color: 'var(--live)',   bg: 'var(--live-bg)'   };
  if (n === 'todo' || n === 'to do' || n === 'open' || n === 'backlog' || n === 'pending')
    return { color: 'var(--amber)',  bg: 'var(--amber-bg)'  };
  if (n === 'blocked' || n === 'stuck')
    return { color: 'var(--red)',    bg: 'var(--red-bg)'    };
  return       { color: 'var(--txt-2)', bg: 'var(--surface-2)' };
}

function priorityStyle(p: string): { color: string } {
  const n = normalize(p);
  if (n === 'high' || n === 'p0' || n === 'p1' || n === 'urgent' || n === 'critical')
    return { color: 'var(--red)'   };
  if (n === 'medium' || n === 'p2' || n === 'med')
    return { color: 'var(--amber)' };
  return { color: 'var(--txt-3)' };
}

function Pill({ label, color, bg }: { label: string; color: string; bg: string }) {
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px',
      borderRadius: 'var(--r-pill)', fontSize: 10.5, fontWeight: 600,
      color, background: bg, whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}

// ── parse mode badge ──────────────────────────────────────────────────────────

function ParseModeBadge({ mode }: { mode: string }) {
  const label =
    mode === 'markdown-table' ? 'table'     :
    mode === 'checklist'      ? 'checklist' :
    'preview';
  const color =
    mode === 'markdown-table' ? 'var(--live)'  :
    mode === 'checklist'      ? 'var(--green)' :
    'var(--txt-3)';
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

// ── constants ─────────────────────────────────────────────────────────────────

const COLS = 'minmax(0,1fr) 100px 110px 80px 90px';

// ── main component ────────────────────────────────────────────────────────────

export function TasksPage() {
  const [data,    setData]    = useState<VaultTasksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // filters
  const [search,         setSearch]         = useState('');
  const [statusFilter,   setStatusFilter]   = useState('');
  const [areaFilter,     setAreaFilter]     = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultTasks();
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // derive unique filter options from loaded tasks
  const allStatuses   = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.status).filter(Boolean))].sort(), [data]);
  const allAreas      = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.area).filter((v): v is string => !!v))].sort(), [data]);
  const allPriorities = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.priority).filter((v): v is string => !!v))].sort(), [data]);

  // client-side filtering
  const filtered = useMemo(() => {
    if (!data?.tasks) return [];
    return data.tasks.filter((t) => {
      if (statusFilter   && t.status   !== statusFilter)   return false;
      if (areaFilter     && t.area     !== areaFilter)     return false;
      if (priorityFilter && t.priority !== priorityFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!t.title.toLowerCase().includes(q) &&
            !(t.area?.toLowerCase().includes(q)) &&
            !(t.source?.toLowerCase().includes(q))) return false;
      }
      return true;
    });
  }, [data, search, statusFilter, areaFilter, priorityFilter]);

  const hasFilters = !!(search || statusFilter || areaFilter || priorityFilter);

  const clearFilters = () => {
    setSearch(''); setStatusFilter(''); setAreaFilter(''); setPriorityFilter('');
  };

  // ── input style ────────────────────────────────────────────────────────────
  const inp: React.CSSProperties = {
    background: 'var(--surface-2)', border: '1px solid var(--line)',
    borderRadius: 'var(--r2)', padding: '5px 9px',
    color: 'var(--txt-0)', fontSize: 12, fontFamily: 'var(--font-ui)',
    outline: 'none',
  };

  return (
    <div style={{ maxWidth: 1080, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* ── header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Tasks</div>
          {data && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
                {data.path}
              </span>
              {data.exists && (
                <>
                  <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>·</span>
                  <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{fmtDate(data.lastModified)}</span>
                  <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>·</span>
                  <span style={{
                    fontSize: 11, fontWeight: 600,
                    color: 'var(--live)', background: 'var(--live-bg)',
                    padding: '1px 7px', borderRadius: 'var(--r-pill)',
                  }}>
                    {data.tasks.length} task{data.tasks.length === 1 ? '' : 's'}
                  </span>
                  <ParseModeBadge mode={data.parseMode} />
                </>
              )}
            </div>
          )}
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* ── error ── */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* ── loading ── */}
      {loading && !data && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {/* ── file not found ── */}
      {data && !data.exists && (
        <EmptyState
          icon="check"
          title="No task file found"
          desc="Expected ops/task-db.md or ops/tasks.md in the configured vault. Create or route a task file from the Raw Inbox."
        />
      )}

      {/* ── preview-only fallback ── */}
      {data?.exists && data.parseMode === 'preview-only' && (
        <>
          <div style={{ padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', fontSize: 12, color: 'var(--amber)', display: 'flex', gap: 6, alignItems: 'flex-start' }}>
            <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
            Task file found, but no structured tasks were detected. Showing preview instead. Supported formats: Markdown table or checklist (<code>- [ ]</code> / <code>- [x]</code>).
          </div>
          {data.preview && (
            <div className="panel panel-pad">
              <pre style={{
                margin: 0, fontFamily: 'var(--font-ui)', fontSize: 12,
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
      {data?.exists && data.tasks.length > 0 && (
        <>
          {/* filter bar */}
          <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tasks…"
              style={{ ...inp, width: 200 }}
            />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ ...inp }}>
              <option value="">All statuses</option>
              {allStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {allAreas.length > 0 && (
              <select value={areaFilter} onChange={(e) => setAreaFilter(e.target.value)} style={{ ...inp }}>
                <option value="">All areas</option>
                {allAreas.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            )}
            {allPriorities.length > 0 && (
              <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ ...inp }}>
                <option value="">All priorities</option>
                {allPriorities.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            )}
            {hasFilters && (
              <button className="btn btn-sm btn-ghost" onClick={clearFilters} style={{ fontSize: 11 }}>
                Clear filters
              </button>
            )}
            {hasFilters && (
              <span style={{ fontSize: 11, color: 'var(--txt-3)', marginLeft: 2 }}>
                {filtered.length} / {data.tasks.length}
              </span>
            )}
          </div>

          {/* no results after filter */}
          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: 'var(--s6)', color: 'var(--txt-3)', fontSize: 12 }}>
              No tasks match the current filters.
            </div>
          )}

          {/* table */}
          {filtered.length > 0 && (
            <div className="panel">
              {/* column headers */}
              <div style={{ display: 'grid', gridTemplateColumns: COLS, gap: 'var(--s3)', padding: '6px var(--s5)', borderBottom: '1px solid var(--line-soft)', alignItems: 'center' }}>
                {['Title', 'Status', 'Area', 'Priority', 'Due'].map((h) => (
                  <span key={h} className="eyebrow" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{h}</span>
                ))}
              </div>

              {/* rows */}
              {filtered.map((task, i) => (
                <TaskRow key={task.id} task={task} last={i === filtered.length - 1} />
              ))}
            </div>
          )}
        </>
      )}

      {/* empty task list (file exists, parseable, but no tasks) */}
      {data?.exists && data.parseMode !== 'preview-only' && data.tasks.length === 0 && (
        <EmptyState
          icon="check"
          title="No tasks found"
          desc={`Task file exists at ${data.path} but contains no parseable tasks.`}
        />
      )}

      {/* ── footer ── */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only. No vault files are modified. Task editing comes in a later sprint.
      </div>

    </div>
  );
}

// ── task row ──────────────────────────────────────────────────────────────────

function TaskRow({ task, last }: { task: VaultTask; last: boolean }) {
  const ss = statusStyle(task.status);
  const ps = task.priority ? priorityStyle(task.priority) : null;

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COLS,
      gap: 'var(--s3)', padding: '9px var(--s5)',
      alignItems: 'center',
      borderBottom: last ? 'none' : '1px solid var(--line-soft)',
    }}>
      {/* title */}
      <div style={{
        fontSize: 12.5, color: 'var(--txt-0)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }} title={task.title}>
        {task.title}
      </div>

      {/* status */}
      <div>
        {task.status
          ? <Pill label={task.status} color={ss.color} bg={ss.bg} />
          : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>
        }
      </div>

      {/* area */}
      <div style={{ fontSize: 11.5, color: 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {task.area ?? <span style={{ color: 'var(--txt-3)' }}>—</span>}
      </div>

      {/* priority */}
      <div style={{ fontSize: 11.5, fontWeight: 600, color: ps?.color ?? 'var(--txt-3)' }}>
        {task.priority ?? '—'}
      </div>

      {/* due */}
      <div style={{ fontSize: 11, color: 'var(--txt-2)' }} className="mono">
        {task.due ?? '—'}
      </div>
    </div>
  );
}
