import type { RouteId } from '@/types';
import { NAV, SYSTEM, AGENT_MODES } from '@/data/mock';
import { useAppStore } from '@/store/useAppStore';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { STATE_TO_TONE } from '@/lib/utils';

const STATUS_PILLS: Array<{ label: string; key: keyof typeof SYSTEM }> = [
  { label: 'OpenClaw',  key: 'openclaw' },
  { label: 'NemoClaw',  key: 'nemoclaw' },
  { label: 'Browser',   key: 'browser'  },
  { label: 'CompUse',   key: 'computer' },
];

interface TopCommandBarProps {
  route: RouteId;
}

export function TopCommandBar({ route }: TopCommandBarProps) {
  const agentMode    = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const openPalette  = useAppStore((s) => s.openPalette);

  const title =
    NAV.flatMap((g) => g.items).find((i) => i.id === route)?.label ?? 'Brain UI';

  return (
    <header
      style={{
        height: 56,
        flexShrink: 0,
        borderBottom: '1px solid var(--line)',
        background: 'var(--bg-1)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--s4)',
        padding: '0 var(--s5)',
      }}
    >
      {/* screen title */}
      <div style={{ fontSize: 14, fontWeight: 600, minWidth: 120, color: 'var(--txt-0)' }}>
        {title}
      </div>

      {/* ⌘K trigger */}
      <button
        onClick={openPalette}
        style={{
          flex: 1,
          maxWidth: 460,
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '7px 12px',
          borderRadius: 'var(--r2)',
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          color: 'var(--txt-2)',
          cursor: 'pointer',
          fontSize: 13,
          fontFamily: 'var(--font-ui)',
          transition: 'border-color var(--fast) var(--ease)',
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--line-strong)'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--line)'; }}
      >
        <Icon name="search" size={14} />
        <span style={{ flex: 1, textAlign: 'left' }}>Search, run a command, jump anywhere…</span>
        <span className="kbd">⌘K</span>
      </button>

      {/* right cluster */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* runtime pills */}
        <div
          style={{
            display: 'flex',
            gap: 10,
            paddingRight: 6,
            borderRight: '1px solid var(--line)',
            marginRight: 4,
          }}
        >
          {STATUS_PILLS.map(({ label, key }) => {
            const svc = SYSTEM[key] as { state: 'ready' | 'idle' | 'partial' | 'disabled' | 'blocked' };
            const tone = STATE_TO_TONE[svc.state];
            return (
              <span
                key={label}
                title={`${label} · ${svc.state}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  fontSize: 11,
                  color: 'var(--txt-2)',
                }}
              >
                <StatusDot tone={tone} />
                {label}
              </span>
            );
          })}
        </div>

        {/* mode dropdown */}
        <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} />
      </div>
    </header>
  );
}
