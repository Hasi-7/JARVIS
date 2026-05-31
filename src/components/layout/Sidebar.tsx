import type { RouteId } from '@/types';
import { NAV } from '@/data/mock';
import { useAppStore } from '@/store/useAppStore';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

interface SidebarProps {
  route: RouteId;
  onNavigate: (route: RouteId) => void;
}

export function Sidebar({ route, onNavigate }: SidebarProps) {
  const agentState = useAppStore((s) => s.agentState);

  return (
    <aside
      style={{
        width: 220,
        flexShrink: 0,
        background: 'var(--bg-1)',
        borderRight: '1px solid var(--line)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* brand */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '16px 18px 14px',
        }}
      >
        <AgentSphere state={agentState} size={30} variant="minimal" />
        <div>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              letterSpacing: '-0.01em',
              color: 'var(--txt-0)',
            }}
          >
            BRAIN UI
          </div>
          <div
            className="mono"
            style={{ fontSize: 9.5, color: 'var(--txt-3)', letterSpacing: '0.04em' }}
          >
            COMMAND CENTER
          </div>
        </div>
      </div>

      <hr className="hairline" />

      {/* nav */}
      <nav
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 10px',
        }}
      >
        {NAV.map((group) => (
          <div key={group.group} style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ padding: '0 8px 6px', fontSize: 9.5 }}>
              {group.group}
            </div>
            {group.items.map((item) => {
              const active = route === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '7px 8px',
                    borderRadius: 'var(--r2)',
                    border: `1px solid ${active ? 'var(--line)' : 'transparent'}`,
                    cursor: 'pointer',
                    marginBottom: 1,
                    fontSize: 13,
                    background: active ? 'var(--surface-2)' : 'transparent',
                    color: active ? 'var(--txt-0)' : 'var(--txt-1)',
                    fontWeight: active ? 600 : 500,
                    fontFamily: 'var(--font-ui)',
                    position: 'relative',
                    transition: 'background var(--fast) var(--ease)',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface)';
                  }}
                  onMouseLeave={(e) => {
                    if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                  }}
                >
                  {active && (
                    <span
                      style={{
                        position: 'absolute',
                        left: -10,
                        top: 8,
                        bottom: 8,
                        width: 2,
                        background: 'var(--live)',
                        borderRadius: 2,
                      }}
                    />
                  )}
                  <span
                    style={{
                      color: active ? 'var(--live)' : 'var(--txt-2)',
                      display: 'flex',
                      flexShrink: 0,
                    }}
                  >
                    <Icon name={item.glyph} size={16} />
                  </span>
                  <span style={{ flex: 1, textAlign: 'left' }}>{item.label}</span>
                  {item.badge != null && (
                    <span
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        minWidth: 18,
                        height: 18,
                        padding: '0 5px',
                        borderRadius: 9,
                        background: active ? 'var(--live-bg)' : 'var(--surface-3)',
                        color: active ? 'var(--live)' : 'var(--txt-2)',
                        display: 'grid',
                        placeItems: 'center',
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <hr className="hairline" />

      {/* footer */}
      <div
        style={{
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <StatusDot tone="green" pulse />
        <span style={{ fontSize: 11, color: 'var(--txt-2)' }}>Vault synced</span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--txt-3)' }}>
          v0.1
        </span>
      </div>
    </aside>
  );
}
