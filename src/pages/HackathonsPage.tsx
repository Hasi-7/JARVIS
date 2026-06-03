import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultHackathon } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

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

function HackathonCard({ hackathon }: { hackathon: VaultHackathon }) {
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
        <button className="btn btn-sm btn-ghost" disabled style={{ fontSize: 10.5, padding: '2px 7px', opacity: 0.35 }} title="Open in Obsidian — not yet implemented">
          Open
        </button>
      </div>
    </div>
  );
}

export function HackathonsPage() {
  const backendConfig  = useAppStore((s) => s.backendConfig);
  const [hackathons, setHackathons] = useState<VaultHackathon[] | null>(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);

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

  const vaultPath = backendConfig?.vaultPath ?? '—';

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Hackathons</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/projects/hackathons/ · raw/hackathons/ — {vaultPath}
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
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
          desc="No .md files in wiki/projects/hackathons/ and no folders in raw/hackathons/. Route hackathon files from the Raw Inbox to populate this page."
        />
      )}

      {/* cards */}
      {hackathons !== null && hackathons.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {hackathons.map((h) => <HackathonCard key={h.id} hackathon={h} />)}
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
        Read-only. No vault files are modified. Data from <span className="mono">wiki/projects/hackathons/</span> and <span className="mono">raw/hackathons/</span>.
      </div>

    </div>
  );
}
