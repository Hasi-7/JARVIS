import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { VaultOpsFile } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  } catch { return iso; }
}

export function ResumePage() {
  const [data,    setData]    = useState<VaultOpsFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultOpsFile('resume-pipeline');
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resume pipeline.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Resume Pipeline</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>ops/resume-pipeline.md</div>
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

      {loading && !data && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>Loading…</div>
      )}

      {data && !data.exists && (
        <div className="panel panel-pad" style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--txt-2)' }}>
          <StatusDot tone="grey" />
          <div>
            <div style={{ fontWeight: 500, fontSize: 13 }}>File not found</div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 2 }}>{data.path}</div>
          </div>
        </div>
      )}

      {data?.exists && (
        <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <StatusDot tone="green" />
              <span className="mono" style={{ fontSize: 11, color: 'var(--txt-1)' }}>{data.path}</span>
            </div>
            <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{fmtDate(data.lastModified)}</span>
          </div>
          {data.preview && (
            <pre style={{
              margin: 0, fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--txt-1)',
              lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: 480, overflowY: 'auto',
              background: 'var(--surface-2)', borderRadius: 'var(--r2)',
              padding: 'var(--s4)', border: '1px solid var(--line)',
            }}>
              {data.preview}
            </pre>
          )}
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only preview — first 2000 characters only. No vault writes occur.
      </div>
    </div>
  );
}
