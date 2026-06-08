import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { EntityCreateResponse, VaultHackathon } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { EntityCreateModal } from '@/components/ui/EntityCreateModal';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function truncate(text: string | null, n = 180): string {
  if (!text) return '';
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text;
}

function HackathonCard({ hackathon, vaultPath }: { hackathon: VaultHackathon; vaultPath: string | null }) {
  const obsidianUrl =
    vaultPath && hackathon.wikiPath
      ? createObsidianOpenUrl(vaultPath, hackathon.wikiPath)
      : null;

  return (
    <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', minHeight: 120 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--txt-0)', lineHeight: 1.3 }}>
        {hackathon.name}
      </div>

      {hackathon.wikiPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="doc" size={11} style={{ color: 'var(--live)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--live)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={hackathon.wikiPath}>
            {hackathon.wikiPath}
          </span>
        </div>
      )}
      {hackathon.rawPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="folder" size={11} style={{ color: 'var(--violet)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--violet)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={hackathon.rawPath}>
            {hackathon.rawPath}
          </span>
        </div>
      )}

      {hackathon.preview && (
        <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5, flex: 1 }}>
          {truncate(hackathon.preview)}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 'var(--s2)' }}>
        <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>{fmtDate(hackathon.lastModified)}</span>

        {obsidianUrl ? (
          <a
            href={obsidianUrl}
            className="btn btn-sm btn-ghost"
            style={{ fontSize: 10.5, padding: '2px 7px', textDecoration: 'none' }}
            title="Open this note in Obsidian"
          >
            Open note
          </a>
        ) : hackathon.rawPath && !hackathon.wikiPath ? (
          <button className="btn btn-sm btn-ghost" disabled style={{ fontSize: 10.5, padding: '2px 7px', opacity: 0.35 }} title="No wiki note — raw folder only">
            Raw folder
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function HackathonsPage() {
  const backendConfig  = useAppStore((s) => s.backendConfig);
  const [hackathons, setHackathons] = useState<VaultHackathon[] | null>(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<EntityCreateResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultHackathons();
      setHackathons(res.hackathons);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load hackathons.');
      setHackathons([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const vaultPath = backendConfig?.vaultPath ?? null;

  async function handleCreate(values: Record<string, string>) {
    setCreateLoading(true);
    setCreateError(null);
    setCreateResult(null);
    try {
      const result = await api.createHackathon({
        name: values.name.trim(),
        date: values.date.trim() || null,
      });
      setCreateResult(result);
      if (result.ok) load();
      else setCreateError(result.stderr || 'Hackathon creation failed.');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Hackathon creation failed.');
    } finally {
      setCreateLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Hackathons</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/projects/hackathons/ · raw/hackathons/ — {vaultPath ?? '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          <button className="btn btn-sm btn-primary" onClick={() => { setCreateOpen(true); setCreateError(null); setCreateResult(null); }}>
            <Icon name="plus" size={13} />
            New Hackathon
          </button>
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
      {loading && hackathons === null && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {/* empty */}
      {!loading && hackathons !== null && hackathons.length === 0 && (
        <EmptyState
          icon="flag"
          title="No hackathons found"
          desc="No .md files in wiki/projects/hackathons/ and no folders in raw/hackathons/. Create a hackathon or route files from the Raw Inbox."
          action={<button className="btn btn-sm btn-primary" onClick={() => setCreateOpen(true)}>New Hackathon</button>}
        />
      )}

      {/* cards */}
      {hackathons !== null && hackathons.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {hackathons.map((h) => <HackathonCard key={h.id} hackathon={h} vaultPath={vaultPath} />)}
        </div>
      )}

      {hackathons !== null && hackathons.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          {hackathons.length} hackathon{hackathons.length === 1 ? '' : 's'} found
        </div>
      )}

      {/* footer */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        New Hackathon runs the safe brain command for this entity type. "Open note" links open Obsidian.
      </div>

      {createOpen && (
        <EntityCreateModal
          title="New Hackathon"
          safetyNote="Runs the safe brain command for this entity type."
          fields={[
            { key: 'name', label: 'Name', placeholder: 'Hackathon name', required: true },
            { key: 'date', label: 'Date', placeholder: 'Optional date' },
          ]}
          loading={createLoading}
          error={createError}
          result={createResult}
          submitLabel="Create hackathon"
          onSubmit={handleCreate}
          onCancel={() => { if (!createLoading) setCreateOpen(false); }}
        />
      )}

    </div>
  );
}
