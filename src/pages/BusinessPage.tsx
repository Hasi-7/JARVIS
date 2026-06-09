import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { EntityCreateResponse, VaultBusinessItem } from '@/lib/api';
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

function truncate(text: string | null, n = 160): string {
  if (!text) return '';
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text;
}

export function BusinessPage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const [entities, setEntities] = useState<VaultBusinessItem[] | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<EntityCreateResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultBusiness();
      setEntities(res.entities);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load business entities.');
      setEntities([]);
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
      const result = await api.createBusinessArea({
        name: values.name.trim(),
        description: values.description.trim() || null,
      });
      setCreateResult(result);
      if (result.ok) load();
      else setCreateError(result.stderr || 'Business area creation failed.');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Business area creation failed.');
    } finally {
      setCreateLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Business</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/business/ · raw/business/ — {vaultPath ?? '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          <button className="btn btn-sm btn-primary" onClick={() => { setCreateOpen(true); setCreateError(null); setCreateResult(null); }}>
            <Icon name="plus" size={13} />
            New Business Area
          </button>
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {loading && entities === null && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading vault…</div>
      )}

      {!loading && entities !== null && entities.length === 0 && (
        <EmptyState
          icon="chart"
          title="No business entities found"
          desc="No .md files in wiki/business/ and no folders in raw/business/. Create a business area or route files from the Raw Inbox."
          action={<button className="btn btn-sm btn-primary" onClick={() => setCreateOpen(true)}>New Business Area</button>}
        />
      )}

      {entities !== null && entities.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {entities.map((e) => {
            const obsidianUrl =
              vaultPath && e.wikiPath
                ? createObsidianOpenUrl(vaultPath, e.wikiPath)
                : null;

            return (
              <div key={e.id} className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{e.name}</div>
                {e.wikiPath && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <Icon name="doc" size={11} style={{ color: 'var(--live)', flexShrink: 0 }} />
                    <span className="mono" style={{ fontSize: 10, color: 'var(--live)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.wikiPath}</span>
                  </div>
                )}
                {e.rawPath && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <Icon name="folder" size={11} style={{ color: 'var(--violet)', flexShrink: 0 }} />
                    <span className="mono" style={{ fontSize: 10, color: 'var(--violet)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.rawPath}</span>
                  </div>
                )}
                {e.preview && <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5 }}>{truncate(e.preview)}</div>}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 'var(--s2)' }}>
                  <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>{fmtDate(e.lastModified)}</span>

                  {obsidianUrl ? (
                    <a
                      href={obsidianUrl}
                      className="btn btn-sm btn-ghost"
                      style={{ fontSize: 10.5, padding: '2px 7px', textDecoration: 'none' }}
                      title="Open this note in Obsidian"
                    >
                      Open note
                    </a>
                  ) : e.rawPath && !e.wikiPath ? (
                    <button className="btn btn-sm btn-ghost" disabled style={{ fontSize: 10.5, padding: '2px 7px', opacity: 0.35 }} title="No wiki note — raw folder only">
                      Raw folder
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        New Business Area scaffolds a wiki note and raw folder. No brain command is used — no files are overwritten.
      </div>

      {createOpen && (
        <EntityCreateModal
          title="New Business Area"
          safetyNote="Scaffolds a wiki note and raw folder using a safe local scaffold. No brain command is used. No files are overwritten."
          fields={[
            { key: 'name', label: 'Name', placeholder: 'Business area name', required: true },
            { key: 'description', label: 'Description', placeholder: 'Optional summary', multiline: true },
          ]}
          loading={createLoading}
          error={createError}
          result={createResult}
          submitLabel="Create business area"
          onSubmit={handleCreate}
          onCancel={() => { if (!createLoading) setCreateOpen(false); }}
        />
      )}
    </div>
  );
}
