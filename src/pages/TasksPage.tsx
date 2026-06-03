import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultTask, VaultTasksResponse, TaskStatus } from '@/lib/api';
import { TASK_STATUSES } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
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

function truncate(s: string, n = 60): string {
  return s.length > n ? s.slice(0, n).trimEnd() + '…' : s;
}

// ── status style helpers ──────────────────────────────────────────────────────

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

function isAllowedStatus(s: string): s is TaskStatus {
  return (TASK_STATUSES as string[]).includes(s.toLowerCase());
}

function normalizeToAllowed(s: string): TaskStatus | '' {
  const lower = s.toLowerCase();
  return isAllowedStatus(lower) ? (lower as TaskStatus) : '';
}

// ── small components ──────────────────────────────────────────────────────────

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

// ── status select (table mode) ────────────────────────────────────────────────

const SELECT_STYLE: React.CSSProperties = {
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 'var(--r-pill)',
  padding: '1px 5px',
  color: 'var(--txt-0)',
  fontSize: 10.5,
  fontFamily: 'var(--font-ui)',
  outline: 'none',
  cursor: 'pointer',
  maxWidth: 96,
};

// ── confirmation modal ────────────────────────────────────────────────────────

interface PendingChange {
  task: VaultTask;
  newStatus: TaskStatus;
}

function ConfirmStatusModal({
  pending,
  taskFilePath,
  updating,
  error,
  onConfirm,
  onCancel,
}: {
  pending: PendingChange;
  taskFilePath: string;
  updating: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const oldStyle = statusStyle(pending.task.status);
  const newStyle = statusStyle(pending.newStatus);

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)',
        backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !updating) onCancel(); }}
    >
      <div
        className="panel"
        style={{
          width: 420, padding: 'var(--s5)',
          display: 'flex', flexDirection: 'column', gap: 'var(--s3)',
          boxShadow: 'var(--shadow-pop)',
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 14 }}>Update task status?</div>

        <div style={{ fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          {truncate(pending.task.title, 72)}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap' }}>
          <Pill
            label={pending.task.status || 'unknown'}
            color={oldStyle.color}
            bg={oldStyle.bg}
          />
          <span style={{ fontSize: 12, color: 'var(--txt-2)' }}>→</span>
          <Pill label={pending.newStatus} color={newStyle.color} bg={newStyle.bg} />
        </div>

        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
          {taskFilePath}
        </div>

        <div style={{
          fontSize: 11, color: 'var(--txt-2)',
          padding: 'var(--s2) var(--s3)',
          background: 'var(--surface-2)', borderRadius: 'var(--r2)',
          border: '1px solid var(--line)',
        }}>
          A backup will be created before writing.
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
          <button
            className="btn btn-sm btn-ghost"
            onClick={onCancel}
            disabled={updating}
          >
            Cancel
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={onConfirm}
            disabled={updating}
          >
            {updating ? 'Applying…' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── constants ─────────────────────────────────────────────────────────────────

const COLS = 'minmax(0,1fr) 100px 110px 80px 90px';

// ── task row ──────────────────────────────────────────────────────────────────

function TaskRow({
  task, last, parseMode, onStatusChange,
}: {
  task:           VaultTask;
  last:           boolean;
  parseMode:      string;
  onStatusChange: (task: VaultTask, newStatus: TaskStatus) => void;
}) {
  const ss = statusStyle(task.status);
  const ps = task.priority ? priorityStyle(task.priority) : null;

  const normalizedStatus = normalizeToAllowed(task.status);
  const hasAllowedStatus = normalizedStatus !== '';

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value;
    if (v && v !== task.status && v !== normalizedStatus) {
      onStatusChange(task, v as TaskStatus);
    } else if (v && v !== task.status) {
      onStatusChange(task, v as TaskStatus);
    }
  }

  function handleCheckboxChange(e: React.ChangeEvent<HTMLInputElement>) {
    onStatusChange(task, e.target.checked ? 'done' : 'todo');
  }

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COLS,
      gap: 'var(--s3)', padding: '9px var(--s5)',
      alignItems: 'center',
      borderBottom: last ? 'none' : '1px solid var(--line-soft)',
    }}>
      {/* title — for checklist, checkbox precedes text */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
        {parseMode === 'checklist' && (
          <input
            type="checkbox"
            checked={task.status === 'done'}
            onChange={handleCheckboxChange}
            style={{
              flexShrink: 0,
              accentColor: 'var(--live)',
              cursor: 'pointer',
              width: 14, height: 14,
            }}
            title="Toggle done"
          />
        )}
        <span style={{
          fontSize: 12.5, color: 'var(--txt-0)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }} title={task.title}>
          {task.title}
        </span>
      </div>

      {/* status */}
      <div>
        {parseMode === 'markdown-table' ? (
          <select
            value={hasAllowedStatus ? normalizedStatus : task.status}
            onChange={handleSelectChange}
            style={SELECT_STYLE}
            title="Change status"
          >
            {!hasAllowedStatus && (
              <option value={task.status} disabled>{task.status || '—'}</option>
            )}
            {TASK_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        ) : task.status ? (
          <Pill label={task.status} color={ss.color} bg={ss.bg} />
        ) : (
          <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>
        )}
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

// ── main component ────────────────────────────────────────────────────────────

export function TasksPage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const showToast     = useAppStore((s) => s.showToast);

  const [data,    setData]    = useState<VaultTasksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // status-edit state
  const [pendingChange, setPendingChange] = useState<PendingChange | null>(null);
  const [updating,      setUpdating]      = useState(false);
  const [updateError,   setUpdateError]   = useState<string | null>(null);

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

  // ── editing ────────────────────────────────────────────────────────────────

  function requestStatusChange(task: VaultTask, newStatus: TaskStatus) {
    if (newStatus === task.status) return;
    setUpdateError(null);
    setPendingChange({ task, newStatus });
  }

  async function applyChange() {
    if (!pendingChange) return;
    setUpdating(true);
    setUpdateError(null);
    try {
      await api.updateVaultTaskStatus(pendingChange.task.id, pendingChange.newStatus);
      const taskTitle = pendingChange.task.title;
      const newSt     = pendingChange.newStatus;
      setPendingChange(null);
      setUpdating(false);
      showToast(`"${truncate(taskTitle, 30)}" → ${newSt}`);
      load();
    } catch (err) {
      setUpdating(false);
      setUpdateError(err instanceof Error ? err.message : 'Update failed.');
    }
  }

  function cancelChange() {
    if (updating) return;
    setPendingChange(null);
    setUpdateError(null);
  }

  // ── filter options from loaded data ────────────────────────────────────────

  const allStatuses   = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.status).filter(Boolean))].sort(), [data]);
  const allAreas      = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.area).filter((v): v is string => !!v))].sort(), [data]);
  const allPriorities = useMemo(() => [...new Set((data?.tasks ?? []).map((t) => t.priority).filter((v): v is string => !!v))].sort(), [data]);

  // ── client-side filtering ──────────────────────────────────────────────────

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

  const vaultPath = backendConfig?.vaultPath ?? null;
  const obsidianUrl =
    vaultPath && data?.exists
      ? createObsidianOpenUrl(vaultPath, data.path)
      : null;

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
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          {obsidianUrl && (
            <a
              href={obsidianUrl}
              className="btn btn-sm btn-ghost"
              style={{ fontSize: 11, textDecoration: 'none' }}
              title="Open this note in Obsidian"
            >
              <Icon name="doc" size={12} style={{ marginRight: 4 }} />
              Open in Obsidian
            </a>
          )}
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>
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
            <span>
              Task file found, but no structured tasks were detected. Showing preview instead.
              Supported formats: Markdown table or checklist (<code>- [ ]</code> / <code>- [x]</code>).
              <strong style={{ display: 'block', marginTop: 3 }}>
                Structured task editing unavailable for this file format.
              </strong>
            </span>
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
                <TaskRow
                  key={task.id}
                  task={task}
                  last={i === filtered.length - 1}
                  parseMode={data.parseMode}
                  onStatusChange={requestStatusChange}
                />
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
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="shield" size={12} />
          Read-only by default. Status edits create a local backup under{' '}
          <span className="mono">backend/data/backups/tasks/</span> before writing.
        </div>
        {data?.parseMode === 'markdown-table' && (
          <div style={{ color: 'var(--txt-3)', paddingLeft: 18 }}>
            Use the status dropdown in each row to update status. A confirmation dialog appears before writing.
          </div>
        )}
        {data?.parseMode === 'checklist' && (
          <div style={{ color: 'var(--txt-3)', paddingLeft: 18 }}>
            Toggle checkboxes to update done/todo. A confirmation dialog appears before writing.
          </div>
        )}
      </div>

      {/* ── confirmation modal ── */}
      {pendingChange && data && (
        <ConfirmStatusModal
          pending={pendingChange}
          taskFilePath={data.path}
          updating={updating}
          error={updateError}
          onConfirm={applyChange}
          onCancel={cancelChange}
        />
      )}

    </div>
  );
}
