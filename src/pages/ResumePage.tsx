import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { ResumePipelineItem, ResumePipelineResponse, ResumePipelineStatus } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

// ── constants ────────────────────────────────────────────────────────────────

const STATUSES: ResumePipelineStatus[] = [
  'new', 'tailoring', 'applied', 'interview', 'offer', 'rejected', 'archived',
];

const STATUS_TONE: Record<string, string> = {
  new:       'var(--txt-2)',
  tailoring: 'var(--live)',
  applied:   'var(--amber)',
  interview: 'var(--amber)',
  offer:     'var(--green)',
  rejected:  'var(--red)',
  archived:  'var(--txt-3)',
};

function statusDot(status: string): 'live' | 'amber' | 'green' | 'grey' | 'red' {
  if (status === 'offer')                    return 'green';
  if (status === 'applied' || status === 'interview') return 'amber';
  if (status === 'tailoring')                return 'live';
  if (status === 'rejected')                 return 'red';
  return 'grey';
}

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch { return iso; }
}

function truncate(text: string | null, n = 80): string {
  if (!text) return '';
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text;
}

function uniq(arr: (string | null)[]): string[] {
  return [...new Set(arr.filter(Boolean) as string[])].sort();
}

function isUrl(s: string | null): boolean {
  if (!s) return false;
  return s.startsWith('http://') || s.startsWith('https://');
}

// ── tailoring prompt ─────────────────────────────────────────────────────────

function generateTailoringPrompt(item: ResumePipelineItem): string {
  const lines: string[] = [];
  lines.push('# Resume Tailoring Prompt');
  lines.push('');
  lines.push(`You are helping tailor a resume and prepare an application for the following opportunity.`);
  lines.push('');
  lines.push(`**Target:** ${item.target}`);
  if (item.company)  lines.push(`**Company:** ${item.company}`);
  if (item.role)     lines.push(`**Role:** ${item.role}`);
  if (item.priority) lines.push(`**Priority:** ${item.priority}`);
  if (item.deadline) lines.push(`**Deadline:** ${item.deadline}`);
  if (item.link)     lines.push(`**Link:** ${item.link}`);
  if (item.notes)    lines.push(`**Notes:** ${item.notes}`);
  lines.push('');
  lines.push('## Your tasks');
  lines.push('');
  lines.push('1. Suggest specific resume bullet edits that better match this role and company.');
  lines.push('2. Identify keywords or skills that are likely missing from a standard resume.');
  lines.push('3. Draft a short cover-letter outline (3–4 bullet points) if this role warrants one.');
  lines.push('4. List the key application prep tasks for this opportunity.');
  lines.push('5. Do NOT invent experience, skills, or credentials the candidate does not have.');
  lines.push('6. If the job description or resume is not provided, ask for it before proceeding.');
  return lines.join('\n');
}

// ── confirm modal ─────────────────────────────────────────────────────────────

interface ConfirmState {
  item:      ResumePipelineItem;
  newStatus: ResumePipelineStatus;
}

function StatusConfirmModal({
  confirm,
  filePath,
  loading,
  error,
  onApply,
  onCancel,
}: {
  confirm:  ConfirmState;
  filePath: string;
  loading:  boolean;
  error:    string | null;
  onApply:  () => void;
  onCancel: () => void;
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
        width: 460, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Update application status</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          <div style={{ fontSize: 12.5, color: 'var(--txt-0)', fontWeight: 500 }}>
            {confirm.item.target}
            {confirm.item.company && (
              <span style={{ color: 'var(--txt-2)', fontWeight: 400 }}>
                {' '}— {confirm.item.company}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span style={{ color: STATUS_TONE[confirm.item.status] ?? 'var(--txt-2)' }}>
              {confirm.item.status}
            </span>
            <Icon name="arrow-right" size={12} style={{ color: 'var(--txt-3)' }} />
            <span style={{ color: STATUS_TONE[confirm.newStatus] ?? 'var(--txt-0)', fontWeight: 600 }}>
              {confirm.newStatus}
            </span>
          </div>
        </div>

        <div style={{
          fontSize: 11, color: 'var(--txt-2)',
          padding: 'var(--s2) var(--s3)',
          background: 'var(--surface-2)', borderRadius: 'var(--r2)',
          border: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3,
        }}>
          <div className="mono" style={{ fontSize: 10.5 }}>{filePath}</div>
          <div style={{ color: 'var(--txt-3)' }}>
            A backup is created before every write. Only the status cell is modified.
          </div>
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

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-sm btn-primary" onClick={onApply} disabled={loading}>
            {loading ? 'Saving…' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── row ───────────────────────────────────────────────────────────────────────

function ResumeRow({
  item,
  onStatusChange,
  onCopyPrompt,
  copiedId,
}: {
  item:           ResumePipelineItem;
  onStatusChange: (item: ResumePipelineItem, s: ResumePipelineStatus) => void;
  onCopyPrompt:   (item: ResumePipelineItem) => void;
  copiedId:       string | null;
}) {
  const copied = copiedId === item.id;

  return (
    <tr style={{ borderBottom: '1px solid var(--line-soft)' }}>
      {/* target */}
      <td style={{ padding: '7px 10px', verticalAlign: 'top' }}>
        <div style={{ fontWeight: 500, fontSize: 12.5, color: 'var(--txt-0)', lineHeight: 1.4 }}>
          {item.target}
        </div>
        {item.notes && (
          <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 2, lineHeight: 1.4 }}>
            {truncate(item.notes, 100)}
          </div>
        )}
      </td>

      {/* company */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.company ? (
          <span style={{ fontSize: 12, color: 'var(--txt-1)' }}>{item.company}</span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* role */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.role ? (
          <span style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>{item.role}</span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* status */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top', minWidth: 140 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <StatusDot tone={statusDot(item.status)} />
          <select
            value={item.status}
            onChange={(e) => onStatusChange(item, e.target.value as ResumePipelineStatus)}
            style={{
              background: 'var(--surface-2)', color: 'var(--txt-0)',
              border: '1px solid var(--line)', borderRadius: 'var(--r1)',
              fontSize: 11, padding: '2px 4px', cursor: 'pointer',
              fontFamily: 'var(--font-ui)',
            }}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </td>

      {/* priority */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.priority ? (
          <span style={{
            fontSize: 10.5,
            color: item.priority.toLowerCase() === 'high' ? 'var(--red)'
              : item.priority.toLowerCase() === 'medium' ? 'var(--amber)'
              : 'var(--txt-2)',
          }}>
            {item.priority}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* deadline */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.deadline ? (
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
            {item.deadline}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* link */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top', maxWidth: 130 }}>
        {item.link ? (
          isUrl(item.link) ? (
            <a
              href={item.link}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 10.5, color: 'var(--live)',
                overflow: 'hidden', textOverflow: 'ellipsis',
                whiteSpace: 'nowrap', display: 'block', maxWidth: 120,
              }}
              title={item.link}
            >
              {item.link.replace(/^https?:\/\//, '').replace(/\/$/, '')}
            </a>
          ) : (
            <span className="mono" style={{
              fontSize: 10, color: 'var(--txt-3)',
              display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={item.link}>
              {item.link}
            </span>
          )
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* actions */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        <button
          className="btn btn-sm btn-ghost"
          style={{ fontSize: 10.5, padding: '2px 8px', whiteSpace: 'nowrap' }}
          onClick={() => onCopyPrompt(item)}
          title="Copy a tailoring prompt for Claude / ChatGPT"
        >
          {copied ? (
            <span style={{ color: 'var(--green)' }}>Copied!</span>
          ) : (
            <>
              <Icon name="copy" size={11} style={{ marginRight: 3 }} />
              Tailor
            </>
          )}
        </button>
      </td>
    </tr>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

const ALL = '__all__';

export function ResumePage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const [data,    setData]    = useState<ResumePipelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // filters
  const [fStatus,  setFStatus]  = useState<string>(ALL);
  const [fCompany, setFCompany] = useState<string>(ALL);
  const [fPriority, setFPriority] = useState<string>(ALL);
  const [fSearch,  setFSearch]  = useState('');

  // status confirm
  const [confirm,        setConfirm]        = useState<ConfirmState | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError,   setConfirmError]   = useState<string | null>(null);

  // copy prompt
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultResumePipeline();
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resume pipeline.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current); }, []);

  const vaultPath  = backendConfig?.vaultPath ?? null;
  const obsidianUrl =
    vaultPath && data?.exists
      ? createObsidianOpenUrl(vaultPath, data.path)
      : null;

  // ── derive filter options ─────────────────────────────────────────────────
  const items        = data?.items ?? [];
  const companyOpts  = uniq(items.map((it) => it.company));
  const priorityOpts = uniq(items.map((it) => it.priority));

  // ── apply filters ─────────────────────────────────────────────────────────
  const filtered = items.filter((it) => {
    if (fStatus   !== ALL && it.status   !== fStatus)   return false;
    if (fCompany  !== ALL && it.company  !== fCompany)  return false;
    if (fPriority !== ALL && it.priority !== fPriority) return false;
    if (fSearch) {
      const q = fSearch.toLowerCase();
      const haystack = [it.target, it.company, it.role, it.status, it.priority, it.deadline, it.notes]
        .filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  // ── handlers ─────────────────────────────────────────────────────────────
  function handleStatusChange(item: ResumePipelineItem, newStatus: ResumePipelineStatus) {
    if (newStatus === item.status) return;
    setConfirm({ item, newStatus });
    setConfirmError(null);
  }

  async function handleConfirmApply() {
    if (!confirm) return;
    setConfirmLoading(true);
    setConfirmError(null);
    try {
      const res = await api.updateResumePipelineStatus(confirm.item.id, confirm.newStatus);
      if (res.ok) {
        setData((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((it) =>
                  it.id === res.item.id ? res.item : it
                ),
              }
            : prev
        );
        setConfirm(null);
      } else {
        setConfirmError('Update failed.');
      }
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : 'Update failed.');
    } finally {
      setConfirmLoading(false);
    }
  }

  function handleCopyPrompt(item: ResumePipelineItem) {
    const prompt = generateTailoringPrompt(item);
    navigator.clipboard.writeText(prompt).then(() => {
      setCopiedId(item.id);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopiedId(null), 2000);
    });
  }

  const selectStyle: React.CSSProperties = {
    background: 'var(--surface-2)', color: 'var(--txt-1)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    fontSize: 11.5, padding: '4px 8px', fontFamily: 'var(--font-ui)',
  };

  const thStyle: React.CSSProperties = {
    fontSize: 10, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.07em',
    padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid var(--line)',
    whiteSpace: 'nowrap',
  };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Resume Pipeline</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            {data?.path ?? 'ops/resume-pipeline.md'}
            {data?.lastModified ? ` · ${fmtDate(data.lastModified)}` : ''}
            {data?.parseMode ? ` · ${data.parseMode}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          {obsidianUrl && (
            <a
              href={obsidianUrl}
              className="btn btn-sm btn-ghost"
              style={{ fontSize: 11, textDecoration: 'none' }}
              title="Open in Obsidian"
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

      {/* error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* loading */}
      {loading && !data && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
      )}

      {/* missing state */}
      {data && !data.exists && (
        <div>
          <EmptyState
            icon="doc"
            title="ops/resume-pipeline.md not found"
            desc="Create ops/resume-pipeline.md in your vault with a Markdown table to use this page. Expected format shown below."
          />
          <div className="panel panel-pad" style={{ marginTop: 'var(--s3)' }}>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 'var(--s2)' }}>
              Expected format
            </div>
            <pre style={{
              margin: 0, fontSize: 11.5, color: 'var(--txt-1)',
              background: 'var(--surface-2)', borderRadius: 'var(--r2)',
              padding: 'var(--s3)', border: '1px solid var(--line)',
              overflowX: 'auto', lineHeight: 1.6,
            }}>
{`| Target | Company | Role | Status | Priority | Deadline | Link | Notes |
|---|---|---|---|---|---|---|---|
| SWE Intern | Acme Corp | Software Engineer Intern | new | high | 2026-09-01 | https://acme.com/careers | Apply via portal |`}
            </pre>
          </div>
        </div>
      )}

      {/* preview-only state */}
      {data?.exists && data.parseMode === 'preview-only' && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', fontSize: 12, marginBottom: 'var(--s3)' }}>
            <StatusDot tone="amber" />
            <span>
              File exists but no Markdown table found — showing raw preview only. Status editing is not available.
            </span>
          </div>
          {data.preview && (
            <div className="panel panel-pad">
              <pre style={{
                margin: 0, fontSize: 11.5, color: 'var(--txt-1)',
                lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                maxHeight: 480, overflowY: 'auto',
              }}>
                {data.preview}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* structured table */}
      {data?.exists && data.parseMode === 'markdown-table' && (
        <>
          {/* filters */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)', alignItems: 'center',
            padding: 'var(--s3) var(--s4)', background: 'var(--surface)',
            borderRadius: 'var(--r2)', border: '1px solid var(--line)',
          }}>
            <input
              type="search"
              placeholder="Search…"
              value={fSearch}
              onChange={(e) => setFSearch(e.target.value)}
              style={{ ...selectStyle, minWidth: 160, background: 'var(--surface-3)' }}
            />
            <select value={fStatus} onChange={(e) => setFStatus(e.target.value)} style={selectStyle}>
              <option value={ALL}>All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {companyOpts.length > 0 && (
              <select value={fCompany} onChange={(e) => setFCompany(e.target.value)} style={selectStyle}>
                <option value={ALL}>All companies</option>
                {companyOpts.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
            {priorityOpts.length > 0 && (
              <select value={fPriority} onChange={(e) => setFPriority(e.target.value)} style={selectStyle}>
                <option value={ALL}>All priorities</option>
                {priorityOpts.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--txt-3)' }}>
              {filtered.length} / {items.length} item{items.length === 1 ? '' : 's'}
            </span>
          </div>

          {/* empty after filter */}
          {filtered.length === 0 && (
            <EmptyState
              icon="filter"
              title="No matching items"
              desc="Adjust the filters or search term."
            />
          )}

          {/* table */}
          {filtered.length > 0 && (
            <div className="panel" style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: 'var(--surface-2)' }}>
                    <th style={thStyle}>Target</th>
                    <th style={thStyle}>Company</th>
                    <th style={thStyle}>Role</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Priority</th>
                    <th style={thStyle}>Deadline</th>
                    <th style={thStyle}>Link</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => (
                    <ResumeRow
                      key={item.id}
                      item={item}
                      onStatusChange={handleStatusChange}
                      onCopyPrompt={handleCopyPrompt}
                      copiedId={copiedId}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* footer */}
      {data?.exists && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="shield" size={12} />
          Status edits create a backup before writing. Only the status cell is modified. No browser automation, job applications, or AI resume generation occurs.
        </div>
      )}

      {/* status confirm modal */}
      {confirm && (
        <StatusConfirmModal
          confirm={confirm}
          filePath={data?.path ?? 'ops/resume-pipeline.md'}
          loading={confirmLoading}
          error={confirmError}
          onApply={handleConfirmApply}
          onCancel={() => { if (!confirmLoading) setConfirm(null); }}
        />
      )}

    </div>
  );
}
