import { useState, useEffect, useRef, useMemo } from 'react';
import type { RouteId, PaletteItem } from '@/types';
import { NAV, QUICK_ACTIONS } from '@/data/mock';
import { Icon } from './Icon';
import { api } from '@/lib/api';
import type { VaultSearchHit } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { useAppStore } from '@/store/useAppStore';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (route: RouteId) => void;
  onCommand: (id: string) => void;
}

export function CommandPalette({ open, onClose, onNavigate, onCommand }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const backendConfig = useAppStore((s) => s.backendConfig);

  // Local vault search (MVP v10). It had no client and no surface at all; the
  // palette is where searching already feels natural, so it lives here rather
  // than becoming another page. Embeddings run on local Ollama, so nothing
  // leaves the machine; without that model it degrades to lexical and says so.
  const [notes, setNotes] = useState<VaultSearchHit[]>([]);
  const [notesDegraded, setNotesDegraded] = useState(false);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const allItems = useMemo<PaletteItem[]>(() => {
    const navItems: PaletteItem[] = NAV.flatMap((g) =>
      g.items.map((it) => ({ kind: 'nav' as const, id: it.id, label: it.label, group: 'Go to', glyph: it.glyph }))
    );
    const actionItems: PaletteItem[] = QUICK_ACTIONS.map((a) => ({
      kind: a.cmd ? 'cmd' as const : 'act' as const,
      id: a.id,
      label: a.label,
      group: a.cmd ? `Run · ${a.cmd}` : 'Action',
      glyph: a.glyph,
    }));
    return [...actionItems, ...navItems];
  }, []);

  const filtered = useMemo(() => {
    const s = query.trim().toLowerCase();
    if (!s) return allItems;
    return allItems.filter((i) => (i.label + ' ' + i.group).toLowerCase().includes(s));
  }, [query, allItems]);

  useEffect(() => { setSel(0); }, [query]);

  useEffect(() => {
    const s = query.trim();
    if (!open || s.length < 3) { setNotes([]); return; }
    // Debounced: the palette filters locally on every keystroke, and the vault
    // index does not need to keep up with typing.
    let alive = true;
    const timer = window.setTimeout(() => {
      api.vaultSearch(s, 5)
        .then((res) => { if (alive) { setNotes(res.results); setNotesDegraded(res.degraded); } })
        .catch(() => { if (alive) { setNotes([]); setNotesDegraded(false); } });
    }, 220);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [query, open]);

  if (!open) return null;

  const run = (item: PaletteItem) => {
    onClose();
    if (item.kind === 'nav') onNavigate(item.id as RouteId);
    else onCommand(item.id);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown')  { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (filtered[sel]) run(filtered[sel]); }
    else if (e.key === 'Escape') { onClose(); }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgb(0 0 0 / 0.5)',
        backdropFilter: 'blur(3px)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(620px, 92vw)',
          background: 'var(--surface)',
          border: '1px solid var(--line-strong)',
          borderRadius: 'var(--r4)',
          boxShadow: 'var(--shadow-pop)',
          overflow: 'hidden',
        }}
      >
        {/* search bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '14px 16px',
            borderBottom: '1px solid var(--line)',
          }}
        >
          <Icon name="cmd" size={17} style={{ color: 'var(--live)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Type a command or search…"
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--txt-0)',
              fontSize: 15,
              fontFamily: 'var(--font-ui)',
            }}
          />
          <span className="kbd">esc</span>
        </div>

        {/* results */}
        <div style={{ maxHeight: 360, overflowY: 'auto', padding: 8 }}>
          {filtered.length === 0 && notes.length === 0 ? (
            <div
              style={{
                padding: 24,
                textAlign: 'center',
                color: 'var(--txt-2)',
                fontSize: 13,
              }}
            >
              No matches
            </div>
          ) : (
            filtered.map((item, i) => (
              <button
                key={item.kind + item.id}
                onMouseEnter={() => setSel(i)}
                onClick={() => run(item)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 11,
                  padding: '9px 11px',
                  borderRadius: 'var(--r2)',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  background: sel === i ? 'var(--surface-3)' : 'transparent',
                  color: 'var(--txt-0)',
                }}
              >
                <span
                  style={{
                    color: sel === i ? 'var(--live)' : 'var(--txt-2)',
                    display: 'flex',
                    flexShrink: 0,
                  }}
                >
                  <Icon name={item.glyph} size={16} />
                </span>
                <span style={{ flex: 1, fontSize: 13.5 }}>{item.label}</span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
                  {item.group}
                </span>
                {sel === i && (
                  <Icon name="enter" size={14} style={{ color: 'var(--txt-2)', flexShrink: 0 }} />
                )}
              </button>
            ))
          )}

          {notes.length > 0 && (
            <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--line-soft)' }}>
              <div className="eyebrow" style={{ padding: '4px 11px 6px', fontSize: 9.5 }}>
                Vault notes{notesDegraded && ' · lexical (no embedding model)'}
              </div>
              {notes.map((hit) => {
                const url = backendConfig?.vaultPath
                  ? createObsidianOpenUrl(backendConfig.vaultPath, hit.path)
                  : null;
                return (
                  <a
                    key={hit.path + hit.heading}
                    href={url ?? undefined}
                    onClick={onClose}
                    style={{
                      display: 'flex', flexDirection: 'column', gap: 2,
                      padding: '7px 11px', borderRadius: 'var(--r2)',
                      textDecoration: 'none', color: 'var(--txt-0)',
                      cursor: url ? 'pointer' : 'default', opacity: url ? 1 : 0.6,
                    }}
                  >
                    <span style={{ fontSize: 12.5 }}>
                      {hit.heading || hit.path.split('/').pop()}
                    </span>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {hit.path}
                    </span>
                    {hit.snippet && (
                      <span style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.4 }}>
                        {hit.snippet.slice(0, 140)}
                      </span>
                    )}
                  </a>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
