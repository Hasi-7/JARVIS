import type { RouteId } from '@/types';
import { NAV, AGENT_MODES } from '@/data/mock';
import { useAppStore } from '@/store/useAppStore';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { resolveModePolicy } from '@/lib/agentModes';
import { useRuntimeStatus, runtimeStatusTone, runtimeStatusLabel } from '@/lib/runtimeStatus';

// These pills previously read from a hardcoded SYSTEM mock and permanently
// showed "Not wired" regardless of what the backend reported.
const STATUS_PILLS: Array<{ label: string; id: string }> = [
  { label: 'OpenClaw',  id: 'openclaw'           },
  { label: 'NemoClaw',  id: 'nemoclaw_openshell' },
  { label: 'Browser',   id: 'browser_harness'    },
  { label: 'CompUse',   id: 'computer_use'       },
];

interface TopCommandBarProps {
  route: RouteId;
}

export function TopCommandBar({ route }: TopCommandBarProps) {
  const agentMode    = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const agentModes   = useAppStore((s) => s.agentModes);
  const openPalette  = useAppStore((s) => s.openPalette);
  const runtime      = useRuntimeStatus();

  const modePolicy = resolveModePolicy(agentMode.id, agentModes);

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
          {STATUS_PILLS.map(({ label, id }) => {
            const item = runtime.items.find((i) => i.id === id);
            const tone = item ? runtimeStatusTone(item) : 'grey';
            const detail = item ? runtimeStatusLabel(item) : 'Unknown';
            return (
              <span
                key={label}
                title={`${label} · ${detail}`}
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

        {/* mode dropdown — shows backend-enforced policy (tooltip + availability) */}
        <span style={{ fontSize: 11, color: 'var(--txt-3)' }}>Mode</span>
        <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} policy={modePolicy} />
      </div>
    </header>
  );
}
