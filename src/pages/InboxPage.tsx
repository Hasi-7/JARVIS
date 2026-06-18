import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { ArchiveResponse, BatchAiClassifyResponse, BrainRunResult, ClassificationProposal, StagedFileInfo } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { EmptyState } from '@/components/ui/EmptyState';
import { StatusDot } from '@/components/ui/StatusDot';
import { ConfidenceBadge } from '@/components/ui/ConfidenceBadge';
import { TagChip } from '@/components/ui/TagChip';
import type { ConfLevel } from '@/types';

// ── types ─────────────────────────────────────────────────────────────────────

interface CombinedEntry {
  file: StagedFileInfo;
  proposal: ClassificationProposal | null;
}

interface EditForm {
  domain: string;
  entity: string;
  sourceType: string;
  proposedDestination: string;
}

type SyncState = 'idle' | 'running' | 'succeeded' | 'failed';

// ── constants ─────────────────────────────────────────────────────────────────

const DOMAINS = [
  'project', 'hackathon', 'course', 'business',
  'research', 'personal', 'chat/session', 'backfill', 'unknown',
];

const SOURCE_TYPES = [
  'notes', 'screenshots', 'session-summaries', 'repo-docs',
  'pitch', 'submission', 'lecture', 'assignment', 'syllabus',
  'past-exam', 'email', 'market-research', 'customer-discovery',
  'finance', 'legal', 'sales', 'content', 'other',
];

const GRID_COLS = '24px minmax(0,1fr) 90px 48px 76px 168px';

// ── helpers ───────────────────────────────────────────────────────────────────

function formatBytes(n: number): string {
  if (n < 1024)    return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch { return iso; }
}

function nowHHMM(): string {
  return new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function isEligible(p: ClassificationProposal | null): boolean {
  return p?.status === 'proposed' || p?.status === 'edited';
}

// ── sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    staged:   { color: 'var(--txt-2)',  bg: 'var(--surface-2)' },
    proposed: { color: 'var(--live)',   bg: 'var(--live-bg)'   },
    edited:   { color: 'var(--amber)',  bg: 'var(--amber-bg)'  },
    approved: { color: 'var(--green)',  bg: 'var(--green-bg)'  },
    skipped:  { color: 'var(--txt-3)',  bg: 'var(--surface-2)' },
    routed:   { color: 'var(--violet)', bg: 'var(--violet-bg)' },
    archived: { color: 'var(--txt-3)',  bg: 'var(--surface-2)' },
  };
  const { color, bg } = cfg[status] ?? cfg.staged;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 'var(--r-pill)',
      fontSize: 10.5, fontWeight: 600, color, background: bg,
      whiteSpace: 'nowrap',
    }}>
      {status}
    </span>
  );
}

// ── sync panel ────────────────────────────────────────────────────────────────

function SyncPanel({
  routedCount,
  syncState,
  syncResult,
  syncError,
  onSync,
  backendConnected,
}: {
  routedCount: number;
  syncState: SyncState;
  syncResult: BrainRunResult | null;
  syncError: string | null;
  onSync: () => void;
  backendConnected: boolean;
}) {
  const btnLabel =
    syncState === 'running'   ? 'Syncing…' :
    syncState === 'succeeded' ? 'Synced' :
    syncState === 'failed'    ? 'Retry sync-raw' :
    'Run brain sync-raw';

  const btnDisabled = syncState === 'running' || !backendConnected;

  return (
    <div className="panel panel-pad">
      {/* header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--s4)', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)' }}>
              Routed files ready to sync
            </span>
            <span style={{
              fontSize: 11, fontWeight: 600, color: 'var(--violet)',
              background: 'var(--violet-bg)', padding: '1px 7px', borderRadius: 'var(--r-pill)',
            }}>
              {routedCount} file{routedCount === 1 ? '' : 's'} routed
            </span>
            {syncState === 'succeeded' && (
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Icon name="check" size={12} />Synced
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--txt-2)', marginTop: 4, lineHeight: 1.5 }}>
            Run <span className="mono" style={{ fontSize: 11 }}>brain sync-raw</span> to update your
            vault intake index. This does not move files; routing already copied them into the vault.
          </div>
        </div>
        <button
          className="btn btn-primary"
          disabled={btnDisabled}
          onClick={onSync}
          style={{ flexShrink: 0 }}
        >
          <Icon
            name="sync"
            size={14}
            style={{ animation: syncState === 'running' ? 'spin 1s linear infinite' : undefined }}
          />
          {btnLabel}
        </button>
      </div>

      {/* sync result output */}
      {(syncResult || syncError) && (
        <div
          style={{
            marginTop: 'var(--s4)',
            borderRadius: 'var(--r2)',
            background: 'var(--surface-2)',
            border: `1px solid ${syncState === 'succeeded' ? 'var(--green-line)' : syncState === 'failed' ? 'var(--red-line)' : 'var(--line)'}`,
            padding: 'var(--s3) var(--s4)',
          }}
        >
          {/* command + status row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
            <StatusDot tone={syncState === 'succeeded' ? 'green' : 'red'} />
            <span className="mono" style={{ fontSize: 11.5, color: 'var(--txt-0)' }}>
              $ brain sync-raw
            </span>
            {syncResult && (
              <span className="mono" style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--txt-3)' }}>
                exit {syncResult.exitCode} · {syncResult.durationMs.toFixed(0)}ms
              </span>
            )}
          </div>

          {/* stdout */}
          {syncResult?.stdout.trim() && (
            <pre
              style={{
                margin: 0, padding: 0,
                fontFamily: 'var(--font-mono)', fontSize: 10.5,
                color: 'var(--txt-1)',
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                maxHeight: 180, overflowY: 'auto',
              }}
            >
              {syncResult.stdout.trim()}
            </pre>
          )}

          {/* stderr */}
          {syncResult?.stderr.trim() && (
            <pre
              style={{
                margin: syncResult.stdout.trim() ? '4px 0 0' : 0, padding: 0,
                fontFamily: 'var(--font-mono)', fontSize: 10.5,
                color: 'var(--red)',
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                maxHeight: 120, overflowY: 'auto',
              }}
            >
              {syncResult.stderr.trim()}
            </pre>
          )}

          {/* network error */}
          {syncError && (
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--red)' }}>
              {syncError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── edit modal ────────────────────────────────────────────────────────────────

function EditModal({
  entry, form, onChange, onSave, onClose, saving, error,
}: {
  entry: CombinedEntry;
  form: EditForm;
  onChange: (f: EditForm) => void;
  onSave: () => void;
  onClose: () => void;
  saving: boolean;
  error: string | null;
}) {
  const inp: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box',
    background: 'var(--surface-2)', border: '1px solid var(--line)',
    borderRadius: 'var(--r2)', padding: '7px 10px',
    color: 'var(--txt-0)', fontSize: 12.5, fontFamily: 'var(--font-ui)', outline: 'none',
  };
  const lbl: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.06em',
    display: 'block', marginBottom: 4,
  };
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.55)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s5)' }}
      onClick={() => !saving && onClose()}>
      <div style={{ width: 'min(500px, 100%)', background: 'var(--surface)', border: '1px solid var(--line-strong)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Edit proposal</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {entry.file.originalName}
            </div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose} disabled={saving} style={{ padding: 4 }}>
            <Icon name="x" size={14} />
          </button>
        </div>
        <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s4)' }}>
            <div>
              <label style={lbl}>Domain</label>
              <select value={form.domain} onChange={(e) => onChange({ ...form, domain: e.target.value })}
                style={{ ...inp, fontFamily: 'var(--font-ui)' }}>
                {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label style={lbl}>Source type</label>
              <select value={form.sourceType} onChange={(e) => onChange({ ...form, sourceType: e.target.value })}
                style={{ ...inp, fontFamily: 'var(--font-ui)' }}>
                {SOURCE_TYPES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={lbl}>Entity</label>
            <input value={form.entity} onChange={(e) => onChange({ ...form, entity: e.target.value })}
              placeholder="Unassigned" style={inp} />
          </div>
          <div>
            <label style={lbl}>Proposed destination</label>
            <input value={form.proposedDestination}
              onChange={(e) => onChange({ ...form, proposedDestination: e.target.value })}
              placeholder="raw/..." className="mono"
              style={{ ...inp, fontFamily: 'var(--font-mono)' }} />
            <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 4 }}>
              Must start with <span className="mono">raw/</span>. No <span className="mono">..</span> or absolute paths.
            </div>
          </div>
          {error && (
            <div style={{ fontSize: 11.5, color: 'var(--red)', display: 'flex', gap: 6, alignItems: 'center' }}>
              <StatusDot tone="red" />{error}
            </div>
          )}
        </div>
        <div style={{ padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={onSave} disabled={saving}>
            <Icon name="check" size={14} />{saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── batch confirm modal ───────────────────────────────────────────────────────

function ConfirmBatchModal({
  count, onConfirm, onCancel, loading,
}: {
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.55)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s5)' }}
      onClick={() => !loading && onCancel()}>
      <div style={{ width: 'min(440px, 100%)', background: 'var(--surface)', border: '1px solid var(--amber-line)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 'var(--s5)' }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 'var(--s3)' }}>
            Approve {count} proposal{count === 1 ? '' : 's'}?
          </div>
          <div style={{ fontSize: 13, color: 'var(--txt-1)', lineHeight: 1.5 }}>
            This will mark them approved for later routing. Files will remain in staging. No vault write will occur.
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 'var(--s4)', padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', fontSize: 11, color: 'var(--amber)' }}>
            <Icon name="shield" size={12} />Routing and vault writes come in a future step.
          </div>
        </div>
        <div style={{ padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onCancel} disabled={loading}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={loading}>
            <Icon name="check" size={14} />{loading ? 'Approving…' : `Approve ${count}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── AI batch classify confirm modal ───────────────────────────────────────────

function ConfirmAiBatchModal({
  count, onConfirm, onCancel, loading,
}: {
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.55)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s5)' }}
      onClick={() => !loading && onCancel()}>
      <div style={{ width: 'min(480px, 100%)', background: 'var(--surface)', border: '1px solid var(--live-line)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 'var(--s5)' }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 'var(--s3)' }}>
            Improve {count} proposal{count === 1 ? '' : 's'} with local AI?
          </div>
          <div style={{ fontSize: 13, color: 'var(--txt-1)', lineHeight: 1.55 }}>
            The model will receive filename metadata only. File contents and vault
            contents will not be sent. Results will remain editable and unapproved.
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 'var(--s4)', padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--live-bg)', border: '1px solid var(--live-line)', fontSize: 11, color: 'var(--live)' }}>
            <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
            <span>Local AI only proposes classification. You still approve before routing.</span>
          </div>
        </div>
        <div style={{ padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onCancel} disabled={loading}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={loading}>
            <Icon name="sync" size={14} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            {loading ? 'Classifying…' : `AI classify ${count}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── route confirm modal ───────────────────────────────────────────────────────

function ConfirmRouteModal({
  entry, vaultPath, onConfirm, onCancel, routing,
}: {
  entry: CombinedEntry;
  vaultPath: string;
  onConfirm: () => void;
  onCancel: () => void;
  routing: boolean;
}) {
  const dest = entry.proposal?.proposedDestination ?? '—';
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.6)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s5)' }}
      onClick={() => !routing && onCancel()}>
      <div style={{ width: 'min(520px, 100%)', background: 'var(--surface)', border: '1px solid var(--amber-line)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon name="folder" size={16} style={{ color: 'var(--amber)', flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Route to vault?</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {entry.file.originalName}
            </div>
          </div>
        </div>
        <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', background: 'var(--surface-2)', padding: 'var(--s4)', borderRadius: 'var(--r2)', border: '1px solid var(--line)' }}>
            {[
              ['File',        entry.file.originalName, 'var(--txt-0)'],
              ['Destination', dest,                    'var(--live)'],
              ['Vault root',  vaultPath,               'var(--txt-2)'],
            ].map(([label, value, color]) => (
              <div key={label} style={{ display: 'flex', gap: 'var(--s3)', fontSize: 12 }}>
                <span style={{ color: 'var(--txt-2)', width: 80, flexShrink: 0 }}>{label}</span>
                <span className="mono" style={{ color, fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', wordBreak: 'break-all' }}>{value}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.55 }}>
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <Icon name="check" size={13} style={{ color: 'var(--green)', marginTop: 2, flexShrink: 0 }} />
              This will <strong>copy</strong> the staged file into your Obsidian vault.
            </div>
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <Icon name="check" size={13} style={{ color: 'var(--green)', marginTop: 2, flexShrink: 0 }} />
              The staged original will remain in <span className="mono" style={{ fontSize: 11 }}>backend/data/staging/</span>.
            </div>
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <Icon name="shield" size={13} style={{ color: 'var(--amber)', marginTop: 2, flexShrink: 0 }} />
              <span className="mono" style={{ fontSize: 11 }}>brain sync-raw</span> will not run automatically.
            </div>
          </div>
        </div>
        <div style={{ padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onCancel} disabled={routing}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={routing}>
            <Icon name="folder" size={14} />{routing ? 'Routing…' : 'Route to vault'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── archive confirm modal ─────────────────────────────────────────────────────

function ConfirmArchiveModal({
  entry, onConfirm, onCancel, archiving,
}: {
  entry: CombinedEntry;
  onConfirm: () => void;
  onCancel: () => void;
  archiving: boolean;
}) {
  const routedPath = entry.proposal?.routedPath ?? entry.proposal?.proposedDestination ?? '—';
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.6)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s5)' }}
      onClick={() => !archiving && onCancel()}>
      <div style={{ width: 'min(520px, 100%)', background: 'var(--surface)', border: '1px solid var(--line-strong)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon name="archive" size={16} style={{ color: 'var(--txt-2)', flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Archive staged original?</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--txt-3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {entry.file.originalName}
            </div>
          </div>
        </div>
        <div style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
          <div style={{ fontSize: 13, color: 'var(--txt-1)', lineHeight: 1.6 }}>
            This moves the staged copy into{' '}
            <span className="mono" style={{ fontSize: 11 }}>backend/data/archive/</span>.
            The routed vault copy remains untouched. Nothing is deleted.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', background: 'var(--surface-2)', padding: 'var(--s4)', borderRadius: 'var(--r2)', border: '1px solid var(--line)' }}>
            {[
              ['File',         entry.file.originalName,     'var(--txt-0)'],
              ['Routed to',    routedPath,                  'var(--violet)'],
              ['Archive dest', 'backend/data/archive/',     'var(--txt-2)'],
            ].map(([label, value, color]) => (
              <div key={label} style={{ display: 'flex', gap: 'var(--s3)', fontSize: 12 }}>
                <span style={{ color: 'var(--txt-2)', width: 88, flexShrink: 0 }}>{label}</span>
                <span className="mono" style={{ color, fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)', fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.55 }}>
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <Icon name="check" size={13} style={{ color: 'var(--green)', marginTop: 2, flexShrink: 0 }} />
              Vault copy at <span className="mono" style={{ fontSize: 11 }}>{routedPath}</span> is not touched.
            </div>
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <Icon name="check" size={13} style={{ color: 'var(--green)', marginTop: 2, flexShrink: 0 }} />
              Nothing is permanently deleted. Archive files can be recovered manually.
            </div>
          </div>
        </div>
        <div style={{ padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onCancel} disabled={archiving}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={archiving}>
            <Icon name="archive" size={14} />{archiving ? 'Archiving…' : 'Archive staged original'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function InboxPage() {
  const navigate               = useAppStore((s) => s.navigate);
  const proposalTarget         = useAppStore((s) => s.proposalTarget);
  const setProposalTarget      = useAppStore((s) => s.setProposalTarget);
  const backendStatus          = useAppStore((s) => s.backendStatus);
  const backendConfig          = useAppStore((s) => s.backendConfig);
  const settings               = useAppStore((s) => s.settings);
  const setStagedCount         = useAppStore((s) => s.setStagedCount);
  const setPendingProposalCount = useAppStore((s) => s.setPendingProposalCount);
  const addCmdEntry            = useAppStore((s) => s.addCmdEntry);
  const showToast              = useAppStore((s) => s.showToast);

  const vaultPath = backendConfig?.vaultPath ?? settings.vaultPath;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef      = useRef<HTMLDivElement>(null);

  const [entries,     setEntries]     = useState<CombinedEntry[]>([]);
  const [loading,     setLoading]     = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [dragOver,    setDragOver]    = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [deletingId,  setDeletingId]  = useState<string | null>(null);
  const [actionId,    setActionId]    = useState<string | null>(null);

  // batch selection
  const [selected,       setSelected]       = useState<Set<string>>(new Set());
  const [showConfirm,    setShowConfirm]    = useState(false);
  const [batchApproving, setBatchApproving] = useState(false);

  // route
  const [routeTarget, setRouteTarget] = useState<CombinedEntry | null>(null);
  const [routing,     setRouting]     = useState(false);

  // sync
  const [syncState,  setSyncState]  = useState<SyncState>('idle');
  const [syncResult, setSyncResult] = useState<BrainRunResult | null>(null);
  const [syncError,  setSyncError]  = useState<string | null>(null);

  // edit modal
  const [editTarget, setEditTarget] = useState<CombinedEntry | null>(null);
  const [editForm,   setEditForm]   = useState<EditForm>({ domain: '', entity: '', sourceType: '', proposedDestination: '' });
  const [editSaving, setEditSaving] = useState(false);
  const [editError,  setEditError]  = useState<string | null>(null);

  // archive
  const [archiveTarget,  setArchiveTarget]  = useState<CombinedEntry | null>(null);
  const [archiving,      setArchiving]      = useState(false);
  const [archivedCount,  setArchivedCount]  = useState(0);

  // AI classification — single row
  const [aiClassifyingId, setAiClassifyingId] = useState<string | null>(null);

  // AI classification — batch
  const [showAiBatchConfirm, setShowAiBatchConfirm] = useState(false);
  const [batchAiClassifying, setBatchAiClassifying] = useState(false);

  // deep-link highlight from Proposal Queue (selection only — no mutation)
  const [highlightId,  setHighlightId]  = useState<string | null>(null);
  const [targetNotice, setTargetNotice] = useState<string | null>(null);
  const pendingTargetRef = useRef<string | null>(null);
  const highlightRef     = useRef<HTMLDivElement | null>(null);

  // ── derived ────────────────────────────────────────────────────────────────
  const eligibleIds = entries.filter((e) => isEligible(e.proposal)).map((e) => e.file.id);
  const selectedEligible = eligibleIds.filter((id) => selected.has(id));
  const allEligibleSelected = eligibleIds.length > 0 && selectedEligible.length === eligibleIds.length;

  // ── load ───────────────────────────────────────────────────────────────────

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [stagedResult, proposalsResult] = await Promise.all([
        api.getStagedFiles(),
        api.getIntakeProposals(),
      ]);
      const proposalMap = new Map(proposalsResult.proposals.map((p) => [p.fileId, p]));
      setEntries(stagedResult.files.map((f) => ({ file: f, proposal: proposalMap.get(f.id) ?? null })));
      setStagedCount(stagedResult.files.length);
      setPendingProposalCount(
        proposalsResult.proposals.filter((p) => p.status === 'proposed' || p.status === 'edited').length
      );
      setArchivedCount(proposalsResult.proposals.filter((p) => p.status === 'archived').length);
      setSelected((prev) => {
        const validIds = new Set(stagedResult.files.map((f) => f.id));
        const next = new Set([...prev].filter((id) => validIds.has(id)));
        return next.size !== prev.size ? next : prev;
      });
    } catch (err) {
      setError(
        backendStatus === 'error'
          ? 'Backend not connected. Start uvicorn to use file staging.'
          : err instanceof Error ? err.message : 'Failed to load.'
      );
    } finally {
      setLoading(false);
    }
  }, [backendStatus, setStagedCount, setPendingProposalCount]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── deep-link from Proposal Queue: highlight the exact staged row ────────────
  // Selection/highlight only — no proposal is approved, routed, or skipped here.
  useEffect(() => {
    if (proposalTarget?.source === 'raw-inbox' && proposalTarget.relatedId) {
      pendingTargetRef.current = proposalTarget.relatedId;
      setProposalTarget(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const targetId = pendingTargetRef.current;
    if (!targetId || loading) return;
    pendingTargetRef.current = null;
    if (entries.some((e) => e.file.id === targetId)) {
      setHighlightId(targetId);
      setTargetNotice('Opened from Proposal Queue.');
    } else {
      setTargetNotice('Target proposal was not found. Showing Raw Inbox.');
    }
  }, [entries, loading]);

  useEffect(() => {
    if (!highlightId) return;
    highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const t = setTimeout(() => setHighlightId(null), 4000);
    return () => clearTimeout(t);
  }, [highlightId]);

  // ── upload ─────────────────────────────────────────────────────────────────

  const handleUpload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadIntakeFiles(files);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  // ── drag / drop ────────────────────────────────────────────────────────────

  const onDragOver  = (e: React.DragEvent) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = (e: React.DragEvent) => {
    if (!dropRef.current?.contains(e.relatedTarget as Node)) setDragOver(false);
  };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    handleUpload(Array.from(e.dataTransfer.files));
  };
  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleUpload(Array.from(e.target.files ?? []));
    e.target.value = '';
  };

  // ── delete ─────────────────────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteStagedFile(id);
      setSelected((prev) => { const n = new Set(prev); n.delete(id); return n; });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeletingId(null);
    }
  };

  // ── individual approve / skip ──────────────────────────────────────────────

  const handleApprove = async (fileId: string) => {
    setActionId(fileId);
    try {
      const updated = await api.approveIntakeProposal(fileId);
      setEntries((prev) => prev.map((e) => e.file.id === fileId ? { ...e, proposal: updated } : e));
      setSelected((prev) => { const n = new Set(prev); n.delete(fileId); return n; });
      setPendingProposalCount(
        entries.filter((e) => e.file.id !== fileId && isEligible(e.proposal)).length
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approve failed.');
    } finally {
      setActionId(null);
    }
  };

  const handleSkip = async (fileId: string) => {
    setActionId(fileId);
    try {
      const updated = await api.skipIntakeProposal(fileId);
      setEntries((prev) => prev.map((e) => e.file.id === fileId ? { ...e, proposal: updated } : e));
      setSelected((prev) => { const n = new Set(prev); n.delete(fileId); return n; });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Skip failed.');
    } finally {
      setActionId(null);
    }
  };

  // ── route ──────────────────────────────────────────────────────────────────

  const handleRoute = async () => {
    if (!routeTarget) return;
    const fileId = routeTarget.file.id;
    setRouteTarget(null);
    setRouting(true);
    setActionId(fileId);
    try {
      const result = await api.routeIntakeProposal(fileId);
      setEntries((prev) =>
        prev.map((e) => e.file.id === fileId ? { ...e, proposal: result.proposal } : e)
      );
      showToast(`Routed → ${result.route.relativePath}`);
      // Reset sync state so the "needs sync" badge appears again for the new routed file
      if (syncState === 'succeeded') setSyncState('idle');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Routing failed.');
    } finally {
      setRouting(false);
      setActionId(null);
    }
  };

  // ── sync ───────────────────────────────────────────────────────────────────

  const handleSync = async () => {
    setSyncState('running');
    setSyncResult(null);
    setSyncError(null);
    const at = nowHHMM();
    try {
      const result = await api.runBrain('sync-raw');
      setSyncResult(result);
      setSyncState(result.ok ? 'succeeded' : 'failed');
      const rawOut = result.stdout.trim() || result.stderr.trim() || (result.ok ? 'Done.' : 'Failed.');
      const out = rawOut.split('\n').find((l) => l.trim()) ?? rawOut;
      addCmdEntry({ cmd: 'brain sync-raw', ok: result.ok, at, out });
      showToast(result.ok ? 'brain sync-raw · done' : 'brain sync-raw · failed');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend not available.';
      setSyncError(msg);
      setSyncState('failed');
      addCmdEntry({ cmd: 'brain sync-raw', ok: false, at, out: msg });
      showToast('brain sync-raw · failed');
    }
  };

  // ── batch approve ──────────────────────────────────────────────────────────

  const handleBatchApprove = async () => {
    setShowConfirm(false);
    setBatchApproving(true);
    try {
      const result = await api.approveIntakeProposalsBatch(selectedEligible);
      const approvedMap = new Map(result.approved.map((p) => [p.fileId, p]));
      setEntries((prev) =>
        prev.map((e) => {
          const updated = approvedMap.get(e.file.id);
          return updated ? { ...e, proposal: updated } : e;
        })
      );
      setSelected(new Set());
      setPendingProposalCount(
        entries.filter((e) => {
          const updated = approvedMap.get(e.file.id);
          const status = updated ? updated.status : e.proposal?.status;
          return status === 'proposed' || status === 'edited';
        }).length
      );
      if (result.skipped.length > 0) {
        setError(
          `${result.approved.length} approved. ` +
          `${result.skipped.length} could not be approved: ` +
          result.skipped.map((s) => s.reason).join('; ')
        );
      } else {
        showToast(`${result.approved.length} proposal${result.approved.length === 1 ? '' : 's'} approved.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Batch approval failed.');
    } finally {
      setBatchApproving(false);
    }
  };

  // ── edit ───────────────────────────────────────────────────────────────────

  const openEdit = (entry: CombinedEntry) => {
    if (!entry.proposal) return;
    setEditForm({
      domain:              entry.proposal.domain,
      entity:              entry.proposal.entity,
      sourceType:          entry.proposal.sourceType,
      proposedDestination: entry.proposal.proposedDestination,
    });
    setEditError(null);
    setEditTarget(entry);
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await api.updateIntakeProposal(editTarget.file.id, editForm);
      await loadAll();
      setEditTarget(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setEditSaving(false);
    }
  };

  // ── archive ────────────────────────────────────────────────────────────────

  const handleArchive = async () => {
    if (!archiveTarget) return;
    const fileId = archiveTarget.file.id;
    setArchiveTarget(null);
    setArchiving(true);
    setActionId(fileId);
    try {
      const result: ArchiveResponse = await api.archiveStagedFile(fileId);
      showToast(`Archived → ${result.archived.archiveName}`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Archive failed.');
    } finally {
      setArchiving(false);
      setActionId(null);
    }
  };

  // ── AI classify ────────────────────────────────────────────────────────────

  const handleAiClassify = async (fileId: string) => {
    setAiClassifyingId(fileId);
    setError(null);
    try {
      const updated = await api.aiClassifyProposal(fileId);
      setEntries((prev) => prev.map((e) => e.file.id === fileId ? { ...e, proposal: updated } : e));
      showToast(`AI classified → ${updated.domain} / ${updated.sourceType}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI classification failed.');
    } finally {
      setAiClassifyingId(null);
    }
  };

  // ── batch AI classify ──────────────────────────────────────────────────────

  const handleBatchAiClassify = async () => {
    setShowAiBatchConfirm(false);
    setBatchAiClassifying(true);
    setError(null);
    try {
      const result: BatchAiClassifyResponse = await api.aiClassifyProposalsBatch(selectedEligible);
      const classifiedMap = new Map(result.classified.map((p) => [p.fileId, p]));
      setEntries((prev) =>
        prev.map((e) => {
          const updated = classifiedMap.get(e.file.id);
          return updated ? { ...e, proposal: updated } : e;
        })
      );
      setSelected(new Set());
      const nc = result.classified.length;
      const ns = result.skipped.length;
      if (ns > 0) {
        setError(
          `AI classified ${nc} proposal${nc === 1 ? '' : 's'}. ` +
          `${ns} skipped: ${result.skipped.map((s) => s.reason).slice(0, 3).join('; ')}`
        );
      } else {
        showToast(`AI classified ${nc} proposal${nc === 1 ? '' : 's'}.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Batch AI classification failed.');
    } finally {
      setBatchAiClassifying(false);
    }
  };

  // ── selection helpers ──────────────────────────────────────────────────────

  const toggleRow = (id: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const toggleSelectAll = () => {
    if (allEligibleSelected) setSelected(new Set());
    else setSelected(new Set(eligibleIds));
  };

  // ── render ─────────────────────────────────────────────────────────────────

  const pending  = entries.filter((e) => isEligible(e.proposal)).length;
  const approved = entries.filter((e) => e.proposal?.status === 'approved').length;
  const routed   = entries.filter((e) => e.proposal?.status === 'routed').length;
  const backendConnected = backendStatus === 'ok';

  return (
    <div style={{ maxWidth: 1080, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* ── drop zone ── */}
      <div ref={dropRef} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? 'var(--live)' : 'var(--line)'}`,
          borderRadius: 'var(--r3)', padding: 'var(--s7)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--s3)',
          background: dragOver ? 'var(--live-bg)' : 'transparent',
          transition: 'border-color var(--fast) var(--ease), background var(--fast) var(--ease)',
          cursor: 'pointer',
        }}>
        <Icon name={uploading ? 'sync' : 'upload'} size={26}
          style={{ color: dragOver ? 'var(--live)' : 'var(--txt-2)', animation: uploading ? 'spin 1s linear infinite' : undefined }} />
        <div style={{ textAlign: 'center', pointerEvents: 'none' }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: dragOver ? 'var(--live)' : 'var(--txt-0)' }}>
            {uploading ? 'Uploading…' : dragOver ? 'Drop to stage' : 'Drop files to stage for classification'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--txt-2)', marginTop: 3 }}>
            Approve proposals → route to vault → run brain sync-raw.
          </div>
        </div>
        <button className="btn btn-sm" disabled={uploading}
          onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
          Browse files
        </button>
        <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={onFileInput} />
      </div>

      {/* ── error banner ── */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12.5, color: 'var(--txt-1)' }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)} style={{ padding: '2px 8px' }}>Dismiss</button>
        </div>
      )}

      {/* ── deep-link notice from Proposal Queue ── */}
      {targetNotice && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', border: '1px solid var(--line)', fontSize: 12.5, color: 'var(--txt-1)' }}>
          <StatusDot tone="live" />
          <span style={{ flex: 1 }}>{targetNotice}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setTargetNotice(null)} style={{ padding: '2px 8px' }}>Dismiss</button>
        </div>
      )}

      {/* ── sync prompt — shown when routed files exist ── */}
      {routed > 0 && (
        <SyncPanel
          routedCount={routed}
          syncState={syncState}
          syncResult={syncResult}
          syncError={syncError}
          onSync={handleSync}
          backendConnected={backendConnected}
        />
      )}

      {/* ── proposal table ── */}
      <div className="panel">

        {/* panel header — normal or batch action bar */}
        {selectedEligible.length > 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap',
            padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--amber-line)',
            background: 'var(--amber-bg)',
          }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--amber)' }}>
              {selectedEligible.length} selected
            </span>
            <button className="btn btn-sm btn-primary" disabled={batchApproving || batchAiClassifying} onClick={() => setShowConfirm(true)}>
              <Icon name="check" size={13} />Approve selected
            </button>
            <button
              className="btn btn-sm btn-ghost"
              style={{ color: 'var(--live)' }}
              disabled={batchApproving || batchAiClassifying}
              title="Improve selected proposals with local AI — metadata only, no auto-approval"
              onClick={() => setShowAiBatchConfirm(true)}
            >
              <Icon name="sync" size={13} style={{ animation: batchAiClassifying ? 'spin 1s linear infinite' : undefined }} />
              {batchAiClassifying ? 'Classifying…' : 'AI classify selected'}
            </button>
            <button className="btn btn-sm btn-ghost" disabled={batchApproving || batchAiClassifying} onClick={() => setSelected(new Set())}>
              Clear selection
            </button>
            <span style={{ fontSize: 11, color: 'var(--amber)', marginLeft: 'auto' }}>
              No vault write · files remain staged
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line-soft)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)' }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {entries.length > 0 ? `Staged · ${entries.length} file${entries.length === 1 ? '' : 's'}` : 'Staged'}
              </span>
              {pending > 0 && (
                <span style={{ fontSize: 11, color: 'var(--amber)', background: 'var(--amber-bg)', padding: '1px 7px', borderRadius: 'var(--r-pill)', fontWeight: 600 }}>
                  {pending} pending
                </span>
              )}
              {approved > 0 && (
                <span style={{ fontSize: 11, color: 'var(--green)', background: 'var(--green-bg)', padding: '1px 7px', borderRadius: 'var(--r-pill)', fontWeight: 600 }}>
                  {approved} approved
                </span>
              )}
              {routed > 0 && (
                <span style={{ fontSize: 11, color: 'var(--violet)', background: 'var(--violet-bg)', padding: '1px 7px', borderRadius: 'var(--r-pill)', fontWeight: 600 }}>
                  {routed} routed
                </span>
              )}
              {loading && <span style={{ fontSize: 11, color: 'var(--txt-3)' }}>Refreshing…</span>}
            </div>
            <button className="btn btn-sm btn-ghost" onClick={loadAll} disabled={loading}>
              <Icon name="sync" size={13} />Refresh
            </button>
          </div>
        )}

        {/* column headers */}
        {entries.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: GRID_COLS, gap: 'var(--s3)', padding: '6px var(--s5)', borderBottom: '1px solid var(--line-soft)', alignItems: 'center' }}>
            <input type="checkbox" checked={allEligibleSelected} disabled={eligibleIds.length === 0}
              onChange={toggleSelectAll}
              style={{ width: 14, height: 14, accentColor: 'var(--live)', cursor: eligibleIds.length > 0 ? 'pointer' : 'default', margin: 0 }} />
            {['File / Destination', 'Domain', 'Conf', 'Status', 'Actions'].map((h) => (
              <span key={h} className="eyebrow" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{h}</span>
            ))}
          </div>
        )}

        {/* rows */}
        {entries.map((entry, i) => {
          const { file, proposal } = entry;
          const eligible   = isEligible(proposal);
          const isRouted   = proposal?.status === 'routed';
          const isSelected = selected.has(file.id);
          const isBusy     = deletingId === file.id || actionId === file.id || batchApproving || routing || archiving || aiClassifyingId === file.id || (batchAiClassifying && selected.has(file.id));
          const isAiClassifying = aiClassifyingId === file.id || (batchAiClassifying && selected.has(file.id));
          const canAiClassify = proposal !== null &&
            !['routed', 'archived'].includes(proposal.status);

          const isHighlighted = highlightId === file.id;

          return (
            <div key={file.id}
              ref={isHighlighted ? highlightRef : undefined}
              style={{
              display: 'grid', gridTemplateColumns: GRID_COLS,
              alignItems: 'center', gap: 'var(--s3)',
              padding: '10px var(--s5)',
              borderBottom: i < entries.length - 1 ? '1px solid var(--line-soft)' : 'none',
              opacity: isBusy ? 0.45 : 1,
              transition: 'opacity var(--fast) var(--ease), box-shadow var(--fast) var(--ease)',
              background: isHighlighted ? 'var(--live-bg)' : isSelected ? 'var(--amber-bg)' : undefined,
              boxShadow: isHighlighted ? 'inset 3px 0 0 var(--live)' : undefined,
            }}>
              {/* checkbox */}
              <div style={{ display: 'flex', alignItems: 'center' }}>
                {eligible ? (
                  <input type="checkbox" checked={isSelected} disabled={isBusy}
                    onChange={() => toggleRow(file.id)}
                    style={{ width: 14, height: 14, accentColor: 'var(--live)', cursor: 'pointer', margin: 0 }} />
                ) : <span style={{ width: 14 }} />}
              </div>

              {/* file name + destination or routed path */}
              <div style={{ minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 12, color: 'var(--txt-0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={file.originalName}>
                  {file.originalName}
                </div>
                {isRouted ? (
                  <div className="mono" style={{ fontSize: 10, color: 'var(--violet)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={proposal?.routedPath ?? ''}>
                    ✓ {proposal?.routedPath ?? proposal?.proposedDestination}
                    {syncState === 'idle' && (
                      <span style={{ color: 'var(--amber)', marginLeft: 8, opacity: 0.8 }}>
                        · needs sync
                      </span>
                    )}
                    {syncState === 'succeeded' && (
                      <span style={{ color: 'var(--green)', marginLeft: 8 }}>
                        · synced
                      </span>
                    )}
                  </div>
                ) : proposal ? (
                  <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={proposal.proposedDestination}>
                    {isAiClassifying
                      ? <span style={{ color: 'var(--live)' }}>Classifying with local AI…</span>
                      : <>
                          → {proposal.proposedDestination}
                          {proposal.classifiedBy === 'local-ai' && (
                            <span style={{ color: 'var(--live)', marginLeft: 6 }}>
                              · AI{proposal.aiModel ? ` (${proposal.aiModel})` : ''}
                            </span>
                          )}
                        </>
                    }
                  </div>
                ) : (
                  <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 2 }}>
                    {formatBytes(file.sizeBytes)} · {formatDate(file.uploadedAt)}
                  </div>
                )}
              </div>

              {/* domain */}
              <div>{proposal ? <TagChip domain={proposal.domain} /> : <span />}</div>

              {/* confidence */}
              <div>{proposal ? <ConfidenceBadge level={proposal.confidence as ConfLevel} /> : <span />}</div>

              {/* status */}
              <StatusBadge status={proposal?.status ?? 'staged'} />

              {/* actions */}
              <div style={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'nowrap' }}>
                {canAiClassify && (
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ fontSize: 11, padding: '3px 7px', color: isAiClassifying ? 'var(--live)' : 'var(--txt-2)', whiteSpace: 'nowrap' }}
                    title="Improve with local AI — proposes classification only, no auto-approval"
                    disabled={isBusy}
                    onClick={() => handleAiClassify(file.id)}
                  >
                    <Icon name="sync" size={11} style={{ animation: isAiClassifying ? 'spin 1s linear infinite' : undefined }} />
                    AI
                  </button>
                )}
                {proposal && !isRouted && (
                  <>
                    <button className="btn btn-sm btn-ghost" style={{ fontSize: 11, padding: '3px 7px' }}
                      title="Edit proposal" disabled={isBusy} onClick={() => openEdit(entry)}>
                      Edit
                    </button>
                    <button className="btn btn-sm btn-ghost"
                      style={{ padding: '3px 6px', color: proposal.status === 'approved' ? 'var(--green)' : undefined }}
                      title="Approve" disabled={isBusy || proposal.status === 'approved'}
                      onClick={() => handleApprove(file.id)}>
                      <Icon name="check" size={12} />
                    </button>
                    <button className="btn btn-sm btn-ghost"
                      style={{ fontSize: 11, padding: '3px 6px', color: proposal.status === 'skipped' ? 'var(--txt-3)' : undefined }}
                      title="Skip" disabled={isBusy || proposal.status === 'skipped'}
                      onClick={() => handleSkip(file.id)}>
                      Skip
                    </button>
                  </>
                )}
                {proposal?.status === 'approved' && (
                  <button className="btn btn-sm btn-ghost"
                    style={{ fontSize: 10.5, padding: '3px 7px', color: 'var(--live)', whiteSpace: 'nowrap' }}
                    title="Route to vault" disabled={isBusy}
                    onClick={() => setRouteTarget(entry)}>
                    Route
                  </button>
                )}
                {isRouted && (
                  <button className="btn btn-sm btn-ghost"
                    style={{ fontSize: 10.5, padding: '3px 7px', color: 'var(--txt-2)', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 3 }}
                    title="Archive staged original — vault copy is untouched" disabled={isBusy}
                    onClick={() => setArchiveTarget(entry)}>
                    <Icon name="archive" size={11} />Archive
                  </button>
                )}
                <button className="btn btn-sm btn-ghost"
                  style={{ padding: '3px 6px', color: 'var(--txt-2)' }}
                  title="Remove staged file" disabled={isBusy}
                  onClick={() => handleDelete(file.id)}>
                  <Icon name="x" size={12} />
                </button>
              </div>
            </div>
          );
        })}

        {/* empty state */}
        {!loading && entries.length === 0 && (
          <EmptyState icon="inbox" title="Inbox clear"
            desc={backendStatus === 'error'
              ? 'Start the backend (uvicorn) then drop files here.'
              : 'Drop files above. Heuristic proposals appear automatically.'}
            action={<button className="btn" onClick={() => navigate('dashboard')}>Back to dashboard</button>}
          />
        )}
        {loading && entries.length === 0 && (
          <div style={{ padding: 'var(--s8)', textAlign: 'center', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
        )}
      </div>

      {/* ── footer note ── */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="shield" size={12} />
          Files in <span className="mono">backend/data/staging/</span>.
          Routing copies files into the vault. Run <span className="mono">brain sync-raw</span> after routing.
          Archive moves staged originals to <span className="mono">backend/data/archive/</span> — vault copies remain untouched.
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="shield" size={12} style={{ color: 'var(--live)' }} />
          Local AI only proposes classification using filename metadata. You still approve before routing. File contents are never sent to the model.
        </div>
        {archivedCount > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 18 }}>
            <Icon name="archive" size={11} />
            Archived staged originals: {archivedCount}
          </div>
        )}
      </div>

      {/* ── modals ── */}
      {editTarget && (
        <EditModal entry={editTarget} form={editForm} onChange={setEditForm}
          onSave={saveEdit} onClose={() => !editSaving && setEditTarget(null)}
          saving={editSaving} error={editError} />
      )}
      {showConfirm && (
        <ConfirmBatchModal count={selectedEligible.length}
          onConfirm={handleBatchApprove} onCancel={() => setShowConfirm(false)}
          loading={batchApproving} />
      )}
      {showAiBatchConfirm && (
        <ConfirmAiBatchModal count={selectedEligible.length}
          onConfirm={handleBatchAiClassify} onCancel={() => setShowAiBatchConfirm(false)}
          loading={batchAiClassifying} />
      )}
      {routeTarget && (
        <ConfirmRouteModal entry={routeTarget} vaultPath={vaultPath}
          onConfirm={handleRoute} onCancel={() => !routing && setRouteTarget(null)}
          routing={routing} />
      )}
      {archiveTarget && (
        <ConfirmArchiveModal entry={archiveTarget}
          onConfirm={handleArchive} onCancel={() => !archiving && setArchiveTarget(null)}
          archiving={archiving} />
      )}
    </div>
  );
}
