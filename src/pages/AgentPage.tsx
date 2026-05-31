import { useAppStore } from '@/store/useAppStore';
import { AGENT_STATES, AGENT_MODES } from '@/data/mock';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { Pill } from '@/components/ui/Pill';

const SPHERE_STATES = Object.keys(AGENT_STATES) as Array<keyof typeof AGENT_STATES>;

export function AgentPage() {
  const agentState    = useAppStore((s) => s.agentState);
  const setAgentState = useAppStore((s) => s.setAgentState);
  const agentMode     = useAppStore((s) => s.agentMode);
  const setAgentMode  = useAppStore((s) => s.setAgentMode);
  const meta          = AGENT_STATES[agentState];

  return (
    <div style={{ display: 'flex', gap: 'var(--s5)', height: '100%', maxWidth: 1200, margin: '0 auto' }}>

      {/* left rail — mode selector */}
      <div style={{ width: 200, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Mode</div>
          {AGENT_MODES.map((m) => {
            const active = m.id === agentMode.id;
            return (
              <button
                key={m.id}
                onClick={() => setAgentMode(m)}
                style={{
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  alignItems: 'flex-start',
                  padding: '8px 10px',
                  marginBottom: 2,
                  borderRadius: 'var(--r2)',
                  border: `1px solid ${active ? 'var(--live-line)' : 'transparent'}`,
                  background: active ? 'var(--live-bg)' : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background var(--fast) var(--ease)',
                }}
              >
                <span style={{ fontSize: 12.5, fontWeight: active ? 600 : 500, color: active ? 'var(--live)' : 'var(--txt-0)' }}>
                  {m.label}
                </span>
                <span style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>{m.desc}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* center — cockpit */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
        {/* cockpit head */}
        <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--s3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Local Agent Cockpit</div>
            <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} />
          </div>

          <AgentSphere
            state={agentState}
            size={80}
            variant="orb"
            count={agentState === 'batch' ? 6 : undefined}
          />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--live)' }}>{meta?.label}</div>
            <div style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>{meta?.blurb}</div>
          </div>
        </div>

        {/* sphere state scrubber */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>State scrubber — demo</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)' }}>
            {SPHERE_STATES.map((s) => {
              const info = AGENT_STATES[s];
              const active = s === agentState;
              return (
                <button
                  key={s}
                  onClick={() => setAgentState(s)}
                  className="btn btn-sm"
                  style={{
                    borderColor: active ? 'var(--live-line)' : undefined,
                    background: active ? 'var(--live-bg)' : undefined,
                    color: active ? 'var(--live)' : undefined,
                  }}
                >
                  {info.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* placeholder conversation */}
        <div className="panel panel-pad" style={{ flex: 1 }}>
          <div className="eyebrow" style={{ marginBottom: 'var(--s4)' }}>Conversation</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <div style={{ maxWidth: '75%', background: 'var(--live-bg)', border: '1px solid var(--live-line)', borderRadius: 'var(--r3)', padding: '10px 14px', fontSize: 13 }}>
                What's the state of my Brain UI project?
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ width: 28, height: 28, flexShrink: 0, marginTop: 2 }}>
                <AgentSphere state="idle" size={28} variant="minimal" />
              </div>
              <div style={{ maxWidth: '75%', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r3)', padding: '10px 14px', fontSize: 13 }}>
                <p style={{ margin: 0, lineHeight: 1.55 }}>
                  Brain UI is your active project. You have 4 raw files staged, 3 escalations queued, and a Claude session ready to consolidate.
                </p>
                <div style={{ display: 'flex', gap: 'var(--s2)', marginTop: 10, flexWrap: 'wrap' }}>
                  <Pill tone="amber">Approve 4 queued changes</Pill>
                  <Pill tone="live">Open Brain UI project</Pill>
                </div>
              </div>
            </div>
          </div>
          {/* composer */}
          <div style={{ marginTop: 'var(--s5)', display: 'flex', gap: 'var(--s2)' }}>
            <input
              placeholder="Send a message… (Enter)"
              style={{
                flex: 1,
                background: 'var(--surface-2)',
                border: '1px solid var(--line)',
                borderRadius: 'var(--r2)',
                padding: '9px 12px',
                fontSize: 13,
                color: 'var(--txt-0)',
                fontFamily: 'var(--font-ui)',
                outline: 'none',
              }}
            />
            <button className="btn btn-primary" style={{ padding: '0 14px' }}>Send</button>
          </div>
        </div>
      </div>

      {/* right rail — stub */}
      <div style={{ width: 280, flexShrink: 0 }}>
        <div className="panel panel-pad" style={{ marginBottom: 'var(--s4)' }}>
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Tool Request</div>
          <div style={{ fontSize: 12, color: 'var(--txt-2)', fontStyle: 'italic' }}>No pending tool requests</div>
        </div>
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Research Run</div>
          <div style={{ fontSize: 12, color: 'var(--txt-2)', fontStyle: 'italic' }}>No active research run</div>
        </div>
      </div>

    </div>
  );
}
