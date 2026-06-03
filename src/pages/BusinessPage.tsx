import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultBusinessItem } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

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

  const vaultPath = backendConfig?.vaultPath ?? '—';

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Business</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/business/ · raw/business/ — {vaultPath}
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
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
          desc="No .md files in wiki/business/ and no folders in raw/business/. Route business files from the Raw Inbox to populate this page."
        />
      )}

      {entities !== null && entities.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {entities.map((e) => (
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
              <div style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 'auto', paddingTop: 'var(--s2)' }}>{fmtDate(e.lastModified)}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only. Data from <span className="mono">wiki/business/</span> and <span className="mono">raw/business/</span>.
      </div>
    </div>
  );
}
