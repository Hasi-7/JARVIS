import { useState, useEffect, useRef, useMemo } from 'react';
import type { RouteId, PaletteItem } from '@/types';
import { NAV, QUICK_ACTIONS } from '@/data/mock';
import { Icon } from './Icon';

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
          {filtered.length === 0 ? (
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
        </div>
      </div>
    </div>
  );
}
