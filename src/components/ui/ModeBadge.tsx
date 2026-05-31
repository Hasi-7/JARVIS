import { useState, useRef, useEffect } from 'react';
import type { AgentMode } from '@/types';
import { Icon } from './Icon';

interface ModeBadgeProps {
  mode: AgentMode;
  modes: AgentMode[];
  onSelect: (mode: AgentMode) => void;
}

export function ModeBadge({ mode, modes, onSelect }: ModeBadgeProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onOutside);
    return () => document.removeEventListener('mousedown', onOutside);
  }, [open]);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        className="btn btn-sm"
        onClick={() => setOpen((o) => !o)}
        style={{
          fontSize: 12,
          gap: 5,
          paddingRight: 8,
          color: 'var(--live)',
          borderColor: 'var(--live-line)',
          background: 'var(--live-bg)',
        }}
      >
        {mode.label}
        <Icon name="chevron-down" size={12} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            zIndex: 120,
            width: 260,
            background: 'var(--surface)',
            border: '1px solid var(--line-strong)',
            borderRadius: 'var(--r3)',
            boxShadow: 'var(--shadow-pop)',
            overflow: 'hidden',
          }}
        >
          {modes.map((m) => {
            const active = m.id === mode.id;
            return (
              <button
                key={m.id}
                onClick={() => { onSelect(m); setOpen(false); }}
                style={{
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 2,
                  padding: '9px 13px',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  background: active ? 'var(--live-bg)' : 'transparent',
                  borderLeft: active ? '2px solid var(--live)' : '2px solid transparent',
                  transition: 'background var(--fast) var(--ease)',
                }}
                onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-2)'; }}
                onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
              >
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: active ? 600 : 500,
                    color: active ? 'var(--live)' : 'var(--txt-0)',
                  }}
                >
                  {m.label}
                </span>
                <span style={{ fontSize: 11, color: 'var(--txt-2)' }}>{m.desc}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
