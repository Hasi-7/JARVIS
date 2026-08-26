import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { ResearchSessionResponse, ResearchSessionSummary, SearchResultItem } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

/**
 * Time-boxed browser research (C1).
 *
 * Starting a session fetches nothing. Opening a page is classified by the
 * Permission Gateway first, and the backend driver refuses unless the OpenShell
 * sandbox guardrail is healthy — browsing fails CLOSED rather than falling back
 * to an unguarded fetch. Captured page text is untrusted and shown for review.
 */

const fieldStyle: React.CSSProperties = {
  width: '100%', background: 'var(--surface-2)',
  border: '1px solid var(--line)', borderRadius: 'var(--r2)',
  padding: '6px 9px', color: 'var(--txt-0)', fontSize: 12.5,
  fontFamily: 'var(--font-ui)', outline: 'none', boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = {
  fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)',
  textTransform: 'uppercase', letterSpacing: '0.07em',
  display: 'block', marginBottom: 4,
};

function statusTone(status: string | null): 'green' | 'amber' | 'red' | 'grey' {
  if (status === 'active') return 'green';
  if (status === 'budget_exhausted') return 'amber';
  if (status === 'stopped') return 'red';
  return 'grey';
}

function statusLabel(status: string | null): string {
  if (status === 'active') return 'Active';
  if (status === 'budget_exhausted') return 'Budget exhausted';
  if (status === 'stopped') return 'Stopped';
  return status ?? 'Unknown';
}

interface Props {
  onUseCaptures?: (payload: { topic: string; rawNotes: string }) => void;
  onUseAsChat?: (payload: { title: string; transcript: string; sourceTool: string }) => void;
}

export function ResearchSessionPanel({ onUseCaptures, onUseAsChat }: Props) {
  const [topic, setTopic]       = useState('');
  const [domains, setDomains]   = useState('');
  const [budget, setBudget]     = useState(300);
  const [current, setCurrent]   = useState<ResearchSessionResponse | null>(null);
  const [history, setHistory]   = useState<ResearchSessionSummary[]>([]);
  const [pageUrl, setPageUrl]   = useState('');
  const [query, setQuery]       = useState('');
  const [hits, setHits]         = useState<SearchResultItem[] | null>(null);
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      setHistory((await api.listResearchSessions()).sessions);
    } catch { /* non-fatal */ }
  }, []);

  useEffect(() => { void loadHistory(); }, [loadHistory]);

  // Poll the active session so the remaining-budget countdown stays truthful.
  useEffect(() => {
    const id = current?.session.id;
    if (!id || current?.session.status !== 'active') return;
    pollRef.current = window.setInterval(async () => {
      try {
        setCurrent(await api.getResearchSession(id));
      } catch { /* non-fatal */ }
    }, 5000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [current?.session.id, current?.session.status]);

  const start = async () => {
    setBusy(true); setError(null);
    try {
      const allowedDomains = domains.split(/[\s,]+/).map((d) => d.trim()).filter(Boolean);
      setCurrent(await api.startResearchSession({ topic, allowedDomains, budgetSeconds: budget }));
      void loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the session.');
    } finally {
      setBusy(false);
    }
  };

  const openPage = async () => {
    const id = current?.session.id;
    if (!id || !pageUrl.trim()) return;
    setBusy(true); setError(null);
    try {
      setCurrent(await api.openResearchPage(id, pageUrl.trim()));
      setPageUrl('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open that page.');
    } finally {
      setBusy(false);
    }
  };

  const runSearch = async () => {
    const id = current?.session.id;
    if (!id || !query.trim()) return;
    setBusy(true); setError(null);
    try {
      setHits((await api.searchInResearchSession(id, query.trim(), 10)).results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed.');
      setHits(null);
    } finally {
      setBusy(false);
    }
  };

  const openResult = async (url: string) => {
    const id = current?.session.id;
    if (!id) return;
    setBusy(true); setError(null);
    try {
      setCurrent(await api.openResearchPage(id, url));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open that result.');
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    const id = current?.session.id;
    if (!id) return;
    setBusy(true); setError(null);
    try {
      setCurrent(await api.stopResearchSession(id));
      void loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not stop the session.');
    } finally {
      setBusy(false);
    }
  };

  const useCaptures = async () => {
    const id = current?.session.id;
    if (!id || !onUseCaptures) return;
    try {
      const payload = await api.researchDraftPayload(id);
      onUseCaptures({ topic: payload.topic, rawNotes: payload.rawNotes });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the draft payload.');
    }
  };

  const useAsChat = async () => {
    const id = current?.session.id;
    if (!id || !onUseAsChat) return;
    try {
      const payload = await api.chatCapturePayload(id);
      onUseAsChat({
        title: payload.conversationTitle,
        transcript: payload.transcript,
        sourceTool: payload.sourceTool,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the chat payload.');
    }
  };

  const session = current?.session;
  const active = session?.status === 'active';

  return (
    <div className="panel" style={{ padding: 'var(--s4) var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StatusDot tone={statusTone(session?.status ?? null)} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>Time-boxed research session</span>
        {session && (
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
            {statusLabel(session.status)} · {Math.round(session.remainingSeconds)}s left ·{' '}
            {session.captureCount} capture{session.captureCount === 1 ? '' : 's'}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {active && (
          <button className="btn btn-sm" onClick={stop} disabled={busy}
                  style={{ background: 'var(--red-bg)', borderColor: 'var(--red-line)' }}>
            Stop now
          </button>
        )}
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <Icon name="shield" size={13} style={{ color: 'var(--amber)', marginTop: 2, flexShrink: 0 }} />
        <span>
          Research runs inside the <strong>OpenShell sandbox</strong>. If the guardrail is not
          healthy, page fetches are <strong>refused</strong> — there is no unguarded fallback.
          An empty domain allowlist denies everything, the wall-clock budget is enforced on every
          fetch, and captured page text is untrusted: it is stored for review and never followed
          as instructions. Nothing reaches the vault until you save a Research draft yourself.
        </span>
      </div>

      {!active && (
        <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 2, minWidth: 200 }}>
            <label style={labelStyle}>Topic</label>
            <input style={fieldStyle} value={topic} onChange={(e) => setTopic(e.target.value)}
                   placeholder="rust ownership semantics" />
          </div>
          <div style={{ flex: 2, minWidth: 200 }}>
            <label style={labelStyle}>Allowed domains (required)</label>
            <input style={fieldStyle} value={domains} onChange={(e) => setDomains(e.target.value)}
                   placeholder="doc.rust-lang.org, developer.mozilla.org" />
          </div>
          <div style={{ width: 110 }}>
            <label style={labelStyle}>Budget (s)</label>
            <input style={fieldStyle} type="number" min={10} max={1800} value={budget}
                   onChange={(e) => setBudget(Number(e.target.value) || 300)} />
          </div>
          <button className="btn btn-sm btn-primary" onClick={start}
                  disabled={busy || !topic.trim() || !domains.trim()}>
            Start session
          </button>
        </div>
      )}

      {active && (
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Open page (must be in the allowlist)</label>
            <input style={fieldStyle} value={pageUrl} onChange={(e) => setPageUrl(e.target.value)}
                   placeholder="https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html" />
          </div>
          <button className="btn btn-sm" onClick={openPage} disabled={busy || !pageUrl.trim()}>
            <Icon name="sync" size={13} style={{ animation: busy ? 'spin 1s linear infinite' : undefined }} />
            Open
          </button>
        </div>
      )}

      {active && (
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Search (results still obey the allowlist)</label>
            <input style={fieldStyle} value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder="rust ownership semantics" />
          </div>
          <button className="btn btn-sm" onClick={runSearch} disabled={busy || !query.trim()}>
            Search
          </button>
        </div>
      )}

      {hits && hits.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {hits.map((h) => (
            <div key={h.url} style={{
              display: 'flex', alignItems: 'center', gap: 'var(--s2)',
              padding: 'var(--s2) var(--s3)', background: 'var(--surface-2)',
              border: '1px solid var(--line)', borderRadius: 'var(--r2)',
              opacity: h.openable ? 1 : 0.6,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{h.title}</div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', wordBreak: 'break-all' }}>
                  {h.url}
                </div>
                {!h.openable && (
                  <div style={{ fontSize: 10, color: 'var(--amber)', marginTop: 2 }}>
                    Blocked — not in this session's allowed domains
                  </div>
                )}
              </div>
              <button className="btn btn-sm btn-ghost" disabled={!h.openable || busy}
                      onClick={() => openResult(h.url)}>
                Open
              </button>
            </div>
          ))}
        </div>
      )}

      {session && session.allowedDomains.length > 0 && (
        <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>
          allowlist: {session.allowedDomains.join(' · ')}
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)' }}>
          {error}
        </div>
      )}

      {current && current.captures.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {current.captures.map((c) => (
            <div key={`${c.url}-${c.timestamp}`} style={{
              padding: 'var(--s3)', background: 'var(--surface-2)',
              border: '1px solid var(--line)', borderRadius: 'var(--r2)',
            }}>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{c.title}</div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 2, wordBreak: 'break-all' }}>
                {c.url}
              </div>
              <div style={{ fontSize: 11, color: 'var(--txt-1)', marginTop: 4, lineHeight: 1.45 }}>
                {c.snippet}
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap' }}>
            {onUseCaptures && (
              <button className="btn btn-sm btn-ghost" onClick={useCaptures}>
                Use captures in a Research draft
              </button>
            )}
            {onUseAsChat && (
              <button className="btn btn-sm btn-ghost" onClick={useAsChat}>
                Use as a Chat Consolidation draft
              </button>
            )}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <details>
          <summary style={{ fontSize: 11, color: 'var(--txt-2)', cursor: 'pointer' }}>
            Past sessions ({history.length})
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
            {history.slice(0, 10).map((h) => (
              <button key={h.id ?? ''} className="btn btn-sm btn-ghost"
                      style={{ justifyContent: 'flex-start' }}
                      onClick={async () => {
                        if (h.id) setCurrent(await api.getResearchSession(h.id));
                      }}>
                <StatusDot tone={statusTone(h.status)} />
                <span style={{ fontSize: 11.5 }}>{h.topic}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>
                  {h.captureCount} capture{h.captureCount === 1 ? '' : 's'}
                </span>
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
