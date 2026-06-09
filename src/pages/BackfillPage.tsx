import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type {
  BackfillItem,
  BackfillResponse,
  BackfillStatus,
  BackfillType,
  BackfillAgent,
  BackfillValue,
  CreateBackfillItemRequest,
} from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

// ── constants ────────────────────────────────────────────────────────────────

const STATUSES: BackfillStatus[] = ['new', 'triaged', 'in-progress', 'done', 'skipped'];
const TYPES: BackfillType[]       = ['project', 'repo', 'hackathon', 'course', 'business', 'other'];
const VALUES: BackfillValue[]     = ['high', 'medium', 'low'];
const AGENTS: BackfillAgent[]     = ['claude-code', 'opencode', 'manual'];

const STATUS_TONE: Record<string, string> = {
  new:           'var(--txt-2)',
  triaged:       'var(--live)',
  'in-progress': 'var(--amber)',
  done:          'var(--green)',
  skipped:       'var(--txt-3)',
};

function statusDot(status: string): 'live' | 'amber' | 'green' | 'grey' | 'red' {
  if (status === 'done')        return 'green';
  if (status === 'in-progress') return 'amber';
  if (status === 'triaged')     return 'live';
  if (status === 'skipped')     return 'grey';
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

// ── closeout prompt ───────────────────────────────────────────────────────────

function generateCloseoutPrompt(item: BackfillItem): string {
  const agentLabel =
    item.agent === 'claude-code' ? 'Claude Code' :
    item.agent === 'opencode'    ? 'OpenCode'    : null;

  const lines: string[] = [];
  lines.push(`# ${agentLabel ?? 'Backfill'} Closeout Prompt`);
  lines.push('');
  lines.push(`You are assisting with a backfill closeout for: **${item.item}**`);
  lines.push('');
  if (item.type)  lines.push(`Type: ${item.type}`);
  if (item.path)  lines.push(`Path/Repo: ${item.path}`);
  if (item.value) lines.push(`Value/Priority: ${item.value}`);
  if (item.notes) lines.push(`Notes: ${item.notes}`);
  if (item.agent) lines.push(`Assigned tool: ${item.agent}`);
  lines.push('');
  lines.push('## Your task');
  lines.push('');
  lines.push('1. Summarize what this was and its purpose.');
  lines.push('2. Identify any useful files, artifacts, or code worth preserving.');
  lines.push('3. Create or update appropriate vault notes for this item.');
  lines.push('4. Produce a list of suggested archive/closeout actions.');
  lines.push('5. Do NOT delete anything.');
  lines.push('6. Ask before taking any destructive or irreversible actions.');
  return lines.join('\n');
}

// ── add backfill item modal ───────────────────────────────────────────────────

interface AddItemFormState {
  item:   string;
  type:   BackfillType;
  status: BackfillStatus;
  value:  BackfillValue | '';
  agent:  BackfillAgent | '';
  path:   string;
  notes:  string;
}

const EMPTY_FORM: AddItemFormState = {
  item:   '',
  type:   'other',
  status: 'new',
  value:  '',
  agent:  '',
  path:   '',
  notes:  '',
};

function AddBackfillItemModal({
  loading,
  error,
  onSubmit,
  onCancel,
}: {
  loading:  boolean;
  error:    string | null;
  onSubmit: (payload: CreateBackfillItemRequest) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<AddItemFormState>(EMPTY_FORM);

  function handleChange(key: keyof AddItemFormState, val: string) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  function handleSubmit() {
    const trimmed = form.item.trim();
    if (!trimmed) return;
    onSubmit({
      item:   trimmed,
      type:   form.type || undefined,
      status: form.status || undefined,
      value:  (form.value || undefined) as BackfillValue | undefined,
      agent:  (form.agent || undefined) as BackfillAgent | undefined,
      path:   form.path.trim() || undefined,
      notes:  form.notes.trim() || undefined,
    });
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3,
    display: 'block',
  };
  const inputStyle: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box',
    background: 'var(--surface-3)', color: 'var(--txt-0)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    fontSize: 12, padding: '5px 8px', fontFamily: 'var(--font-ui)',
  };
  const selectStyle: React.CSSProperties = { ...inputStyle, cursor: 'pointer' };

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
        width: 520, maxHeight: '90vh', overflowY: 'auto',
        padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>New Backfill Item</div>

        {/* item */}
        <div>
          <label style={labelStyle}>Item <span style={{ color: 'var(--red)' }}>*</span></label>
          <input
            style={inputStyle}
            type="text"
            placeholder="e.g. old-payments-repo, Hackathon 2023, Advanced SQL course…"
            value={form.item}
            onChange={(e) => handleChange('item', e.target.value)}
            disabled={loading}
            autoFocus
          />
        </div>

        {/* type + status row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Type</label>
            <select style={selectStyle} value={form.type} onChange={(e) => handleChange('type', e.target.value)} disabled={loading}>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Status</label>
            <select style={selectStyle} value={form.status} onChange={(e) => handleChange('status', e.target.value)} disabled={loading}>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* value + agent row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)' }}>
          <div>
            <label style={labelStyle}>Value</label>
            <select style={selectStyle} value={form.value} onChange={(e) => handleChange('value', e.target.value)} disabled={loading}>
              <option value="">none</option>
              {VALUES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Agent</label>
            <select style={selectStyle} value={form.agent} onChange={(e) => handleChange('agent', e.target.value)} disabled={loading}>
              <option value="">none</option>
              {AGENTS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        {/* path */}
        <div>
          <label style={labelStyle}>Path / Repo</label>
          <input
            style={inputStyle}
            type="text"
            placeholder="D:\path\to\repo or /home/user/project  (optional)"
            value={form.path}
            onChange={(e) => handleChange('path', e.target.value)}
            disabled={loading}
          />
        </div>

        {/* notes */}
        <div>
          <label style={labelStyle}>Notes</label>
          <textarea
            style={{ ...inputStyle, resize: 'vertical', minHeight: 60 }}
            placeholder="Any context worth capturing  (optional)"
            value={form.notes}
            onChange={(e) => handleChange('notes', e.target.value)}
            disabled={loading}
          />
        </div>

        {/* safety note */}
        <div style={{
          fontSize: 11, color: 'var(--txt-3)',
          padding: 'var(--s2) var(--s3)',
          background: 'var(--surface-2)', borderRadius: 'var(--r2)',
          border: '1px solid var(--line)',
          display: 'flex', alignItems: 'flex-start', gap: 6,
        }}>
          <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
          <span>
            This adds a backfill row only. It does not scan repos, launch agents, or modify referenced paths.
          </span>
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
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={handleSubmit}
            disabled={loading || !form.item.trim()}
          >
            {loading ? 'Adding…' : 'Add Backfill Item'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── confirm modal ─────────────────────────────────────────────────────────────

interface ConfirmState {
  item:      BackfillItem;
  newStatus: BackfillStatus;
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
        <div style={{ fontWeight: 700, fontSize: 14 }}>Update backfill status</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          <div style={{ fontSize: 12.5, color: 'var(--txt-0)', fontWeight: 500 }}>
            {confirm.item.item}
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

function BackfillRow({
  item,
  onStatusChange,
  onCopyPrompt,
  copiedId,
}: {
  item:           BackfillItem;
  onStatusChange: (item: BackfillItem, s: BackfillStatus) => void;
  onCopyPrompt:   (item: BackfillItem) => void;
  copiedId:       string | null;
}) {
  const copied = copiedId === item.id;

  return (
    <tr style={{ borderBottom: '1px solid var(--line-soft)' }}>
      {/* item */}
      <td style={{ padding: '7px 10px', verticalAlign: 'top' }}>
        <div style={{ fontWeight: 500, fontSize: 12.5, color: 'var(--txt-0)', lineHeight: 1.4 }}>
          {item.item}
        </div>
        {item.notes && (
          <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 2, lineHeight: 1.4 }}>
            {truncate(item.notes, 100)}
          </div>
        )}
      </td>

      {/* type */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.type ? (
          <span style={{
            fontSize: 10.5, color: 'var(--live)',
            background: 'var(--live-bg)', border: '1px solid var(--live-line)',
            borderRadius: 'var(--r1)', padding: '1px 6px',
          }}>
            {item.type}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* status */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top', minWidth: 130 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <StatusDot tone={statusDot(item.status)} />
          <select
            value={item.status}
            onChange={(e) => onStatusChange(item, e.target.value as BackfillStatus)}
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

      {/* value */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.value ? (
          <span style={{
            fontSize: 10.5,
            color: item.value.toLowerCase() === 'high' ? 'var(--red)'
              : item.value.toLowerCase() === 'medium' ? 'var(--amber)'
              : 'var(--txt-2)',
          }}>
            {item.value}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* path */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top', maxWidth: 200 }}>
        {item.path ? (
          <span className="mono" style={{
            fontSize: 10, color: 'var(--txt-2)',
            display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }} title={item.path}>
            {item.path}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* agent */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        {item.agent ? (
          <span style={{
            fontSize: 10.5, color: 'var(--violet)',
            background: 'var(--violet-bg)', border: '1px solid var(--violet-line)',
            borderRadius: 'var(--r1)', padding: '1px 6px',
          }}>
            {item.agent}
          </span>
        ) : <span style={{ color: 'var(--txt-3)', fontSize: 11 }}>—</span>}
      </td>

      {/* actions */}
      <td style={{ padding: '7px 8px', verticalAlign: 'top' }}>
        <button
          className="btn btn-sm btn-ghost"
          style={{ fontSize: 10.5, padding: '2px 8px', whiteSpace: 'nowrap' }}
          onClick={() => onCopyPrompt(item)}
          title="Copy a closeout prompt for Claude Code / OpenCode"
        >
          {copied ? (
            <span style={{ color: 'var(--green)' }}>Copied!</span>
          ) : (
            <>
              <Icon name="copy" size={11} style={{ marginRight: 3 }} />
              Copy prompt
            </>
          )}
        </button>
      </td>
    </tr>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

const ALL = '__all__';

export function BackfillPage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const [data,    setData]    = useState<BackfillResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // filters
  const [fStatus, setFStatus] = useState<string>(ALL);
  const [fType,   setFType]   = useState<string>(ALL);
  const [fValue,  setFValue]  = useState<string>(ALL);
  const [fAgent,  setFAgent]  = useState<string>(ALL);
  const [fSearch, setFSearch] = useState('');

  // status confirm
  const [confirm,        setConfirm]        = useState<ConfirmState | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError,   setConfirmError]   = useState<string | null>(null);

  // add item modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [addLoading,   setAddLoading]   = useState(false);
  const [addError,     setAddError]     = useState<string | null>(null);

  // create file
  const [createFileLoading, setCreateFileLoading] = useState(false);
  const [createFileError,   setCreateFileError]   = useState<string | null>(null);

  // copy prompt
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultBackfill();
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load backfill.');
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

  // ── detect fallback-only state ────────────────────────────────────────────
  const isFallbackOnly = data?.exists === true && data.path === 'ops/backfill-last-year.md';
  const isPrimary      = data?.exists === true && data.path === 'ops/backfill.md';
  const canAddItems    = isPrimary && data?.parseMode === 'markdown-table';

  // ── derive filter options from loaded items ───────────────────────────────
  const items = data?.items ?? [];
  const typeOpts  = uniq(items.map((it) => it.type));
  const valueOpts = uniq(items.map((it) => it.value));
  const agentOpts = uniq(items.map((it) => it.agent));

  // ── apply filters ─────────────────────────────────────────────────────────
  const filtered = items.filter((it) => {
    if (fStatus !== ALL && it.status !== fStatus) return false;
    if (fType   !== ALL && it.type   !== fType)   return false;
    if (fValue  !== ALL && it.value  !== fValue)  return false;
    if (fAgent  !== ALL && it.agent  !== fAgent)  return false;
    if (fSearch) {
      const q = fSearch.toLowerCase();
      const haystack = [it.item, it.type, it.status, it.value, it.path, it.notes, it.agent]
        .filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  // ── handlers ─────────────────────────────────────────────────────────────

  async function handleCreateFile() {
    setCreateFileLoading(true);
    setCreateFileError(null);
    try {
      await api.createBackfillFile();
      await load();
    } catch (err) {
      setCreateFileError(err instanceof Error ? err.message : 'Failed to create file.');
    } finally {
      setCreateFileLoading(false);
    }
  }

  async function handleAddItem(payload: CreateBackfillItemRequest) {
    setAddLoading(true);
    setAddError(null);
    try {
      await api.createBackfillItem(payload);
      setShowAddModal(false);
      await load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to add item.');
    } finally {
      setAddLoading(false);
    }
  }

  function handleStatusChange(item: BackfillItem, newStatus: BackfillStatus) {
    if (newStatus === item.status) return;
    setConfirm({ item, newStatus });
    setConfirmError(null);
  }

  async function handleConfirmApply() {
    if (!confirm) return;
    setConfirmLoading(true);
    setConfirmError(null);
    try {
      const res = await api.updateBackfillStatus(confirm.item.id, confirm.newStatus);
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

  function handleCopyPrompt(item: BackfillItem) {
    const prompt = generateCloseoutPrompt(item);
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
    <div style={{ maxWidth: 1060, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Backfill</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            {data?.path ?? 'ops/backfill.md'}
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
          {canAddItems && (
            <button
              className="btn btn-sm btn-primary"
              onClick={() => { setAddError(null); setShowAddModal(true); }}
              disabled={loading}
            >
              <Icon name="plus" size={12} style={{ marginRight: 4 }} />
              New Backfill Item
            </button>
          )}
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

      {/* fallback-only state: ops/backfill-last-year.md exists, ops/backfill.md missing */}
      {isFallbackOnly && (
        <div style={{
          padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)',
          background: 'var(--amber-bg)', border: '1px solid var(--amber-line)',
          fontSize: 12, display: 'flex', flexDirection: 'column', gap: 'var(--s2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusDot tone="amber" />
            <span>
              Reading from <span className="mono" style={{ fontSize: 10.5 }}>ops/backfill-last-year.md</span>.
              New items can only be added to <span className="mono" style={{ fontSize: 10.5 }}>ops/backfill.md</span>.
            </span>
          </div>
          {createFileError && (
            <div style={{ fontSize: 11.5, color: 'var(--red)', paddingLeft: 20 }}>{createFileError}</div>
          )}
          <div style={{ paddingLeft: 20 }}>
            <button
              className="btn btn-sm btn-primary"
              onClick={handleCreateFile}
              disabled={createFileLoading}
            >
              {createFileLoading ? 'Creating…' : 'Create ops/backfill.md'}
            </button>
          </div>
        </div>
      )}

      {/* missing state */}
      {data && !data.exists && (
        <div>
          <EmptyState
            icon="doc"
            title="ops/backfill.md not found"
            desc="No backfill file found. Create the starter file to begin capturing prior work."
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
{`| Item | Type | Status | Value | Path | Agent | Notes |
|---|---|---|---|---|---|---|
| Example repo | repo | new | high | D:\\path\\repo | claude-code | Needs closeout |`}
            </pre>
            {createFileError && (
              <div style={{ marginTop: 'var(--s2)', fontSize: 11.5, color: 'var(--red)' }}>{createFileError}</div>
            )}
            <div style={{ marginTop: 'var(--s3)' }}>
              <button
                className="btn btn-sm btn-primary"
                onClick={handleCreateFile}
                disabled={createFileLoading}
              >
                {createFileLoading ? 'Creating…' : 'Create Backfill file'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* preview-only state */}
      {data?.exists && data.parseMode === 'preview-only' && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', fontSize: 12, marginBottom: 'var(--s3)' }}>
            <StatusDot tone="amber" />
            <span>
              File exists but no Markdown table found — showing raw preview only. Status editing and new items are not available.
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
              style={{
                ...selectStyle,
                minWidth: 160,
                background: 'var(--surface-3)',
              }}
            />
            <select value={fStatus} onChange={(e) => setFStatus(e.target.value)} style={selectStyle}>
              <option value={ALL}>All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {typeOpts.length > 0 && (
              <select value={fType} onChange={(e) => setFType(e.target.value)} style={selectStyle}>
                <option value={ALL}>All types</option>
                {typeOpts.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
            {valueOpts.length > 0 && (
              <select value={fValue} onChange={(e) => setFValue(e.target.value)} style={selectStyle}>
                <option value={ALL}>All values</option>
                {valueOpts.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
            {agentOpts.length > 0 && (
              <select value={fAgent} onChange={(e) => setFAgent(e.target.value)} style={selectStyle}>
                <option value={ALL}>All agents</option>
                {agentOpts.map((v) => <option key={v} value={v}>{v}</option>)}
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
                    <th style={thStyle}>Item</th>
                    <th style={thStyle}>Type</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Value</th>
                    <th style={thStyle}>Path</th>
                    <th style={thStyle}>Agent</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => (
                    <BackfillRow
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
          Writes create a timestamped backup before modifying. Only ops/backfill.md is written. No repos, vault notes, or Claude/OpenCode processes are affected.
        </div>
      )}

      {/* status confirm modal */}
      {confirm && (
        <StatusConfirmModal
          confirm={confirm}
          filePath={data?.path ?? 'ops/backfill.md'}
          loading={confirmLoading}
          error={confirmError}
          onApply={handleConfirmApply}
          onCancel={() => { if (!confirmLoading) setConfirm(null); }}
        />
      )}

      {/* add item modal */}
      {showAddModal && (
        <AddBackfillItemModal
          loading={addLoading}
          error={addError}
          onSubmit={handleAddItem}
          onCancel={() => { if (!addLoading) { setShowAddModal(false); setAddError(null); } }}
        />
      )}

    </div>
  );
}
