import { useState } from 'react';
import {
  TODAY, APPROVALS, SYSTEM, AGENT_STATES, AGENT_MODES,
  QUICK_ACTIONS, CONSOLIDATED,
} from '@/data/mock';
import { useAppStore } from '@/store/useAppStore';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';
import { SourceGlyph } from '@/components/ui/SourceGlyph';
import { StatusCard } from '@/components/dashboard/StatusCard';
import { PlanBlock } from '@/components/dashboard/PlanBlock';
import { ApprovalRow } from '@/components/dashboard/ApprovalRow';
import { SystemRow } from '@/components/dashboard/SystemRow';
import type { RouteId, SystemService } from '@/types';

// brain subcommands wired to the backend (mirrors AppShell mapping)
const BRAIN_ACTION_MAP: Record<string, string> = {
  today:     'today',
  weekly:    'weekly',
  syncraw:   'sync-raw',
  calexport: 'calendar-export',
};

export function DashboardPage() {
  const agentState      = useAppStore((s) => s.agentState);
  const agentMode       = useAppStore((s) => s.agentMode);
  const setAgentMode    = useAppStore((s) => s.setAgentMode);
  const navigate        = useAppStore((s) => s.navigate);
  const showToast       = useAppStore((s) => s.showToast);
  const settings        = useAppStore((s) => s.settings);
  const backendStatus   = useAppStore((s) => s.backendStatus);
  const backendConfig   = useAppStore((s) => s.backendConfig);
  const cmdLog          = useAppStore((s) => s.cmdLog);
  const runBrainCommand = useAppStore((s) => s.runBrainCommand);
  const stagedCount            = useAppStore((s) => s.stagedCount);
  const pendingProposalCount   = useAppStore((s) => s.pendingProposalCount);
  const agentStatus     = useAppStore((s) => s.agentStatus);
  const setAgentPrefill = useAppStore((s) => s.setAgentPrefill);

  const [ask, setAsk] = useState('');

  const meta = AGENT_STATES[agentState];

  const runCommand = (id: string) => {
    if (id === 'ask')         return navigate('agent');
    if (id === 'research')    return navigate('research');
    if (id === 'consolidate') return navigate('consolidate');
    if (id === 'upload')      return navigate('inbox');
    const brainCmd = BRAIN_ACTION_MAP[id];
    if (brainCmd) { runBrainCommand(brainCmd); return; }
    const a = QUICK_ACTIONS.find((x) => x.id === id);
    if (a) showToast(a.cmd ? `${a.cmd} (not wired yet)` : `Opened ${a.label}`);
  };

  const submitAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ask.trim()) return;
    setAgentPrefill(ask.trim());
    navigate('agent');
    setAsk('');
  };

  const counts = [
    { label: 'Approvals',    value: pendingProposalCount, sub: 'file proposals',  tone: 'amber'  as const, nav: 'inbox'     as RouteId, accent: true },
    { label: 'Raw pending',  value: stagedCount,      sub: 'staged files',    tone: 'live'   as const, nav: 'inbox'     as RouteId },
    { label: 'Escalations',  value: 3,                sub: '1 in progress',   tone: 'violet' as const, nav: 'escalation'as RouteId },
    { label: 'Calendar',     value: 3,                sub: 'candidates',      tone: 'live'   as const, nav: 'calendar'  as RouteId },
    { label: 'Backfill',     value: '34%',            sub: '11 / 32 repos',   icon: 'layers',           nav: 'backfill'  as RouteId },
    { label: 'Resume',       value: 6,                sub: 'evidence rows',   icon: 'doc',              nav: 'resume'    as RouteId },
  ];

  // Dynamic runtime services derived from backend state
  const backendService: SystemService =
    backendStatus === 'ok'      ? { state: 'ready',    label: 'Backend',   detail: 'FastAPI · localhost:8000' }
    : backendStatus === 'error' ? { state: 'blocked',  label: 'Backend',   detail: 'Not connected · start uvicorn' }
    :                             { state: 'idle',     label: 'Backend',   detail: 'Checking…' };

  const brainService: SystemService =
    backendStatus === 'ok'
      ? { state: 'ready',    label: 'Brain CLI', detail: backendConfig?.brainCmd ?? 'Connected' }
      : { state: 'disabled', label: 'Brain CLI', detail: 'Backend not connected' };

  const localModelService: SystemService =
    agentStatus === null
      ? { state: 'idle',     label: 'Local model', detail: 'Checking…' }
      : agentStatus.available
        ? { state: 'ready',  label: 'Local model', detail: `${agentStatus.model} · ${agentStatus.provider}` }
        : { state: 'partial',label: 'Local model', detail: agentStatus.message.slice(0, 52) };

  // Vault path: prefer backend config, fall back to frontend localStorage setting
  const vaultDisplay = backendConfig?.vaultPath ?? settings.vaultPath;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)', maxWidth: 1320, margin: '0 auto' }}>

      {/* ── header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--s4)', flexWrap: 'wrap' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 4 }}>
            {TODAY.date} · Good afternoon, Hasnain
          </div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: '-0.015em', color: 'var(--txt-0)' }}>
            Today's focus
          </h1>
          <div style={{ fontSize: 14, color: 'var(--txt-1)', marginTop: 2 }}>{TODAY.focus}</div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)' }}>
          <button className="btn" onClick={() => runCommand('today')}>
            <Icon name="sun" size={15} />Run today
          </button>
          <button className="btn" onClick={() => runCommand('weekly')}>
            <Icon name="cal" size={15} />Weekly
          </button>
          <button className="btn btn-primary" onClick={() => navigate('inbox')}>
            <Icon name="upload" size={15} />Upload raw
          </button>
        </div>
      </div>

      {/* ── count strip ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--s3)' }}>
        {counts.map((c) => (
          <StatusCard
            key={c.label}
            label={c.label}
            value={c.value}
            sub={c.sub}
            tone={c.tone}
            icon={'icon' in c ? c.icon : undefined}
            accent={c.accent}
            onClick={() => navigate(c.nav)}
          />
        ))}
      </div>

      {/* ── main 2-col grid ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.9fr) minmax(320px, 1fr)',
          gap: 'var(--s5)',
          alignItems: 'start',
        }}
      >
        {/* ── left column ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

          {/* today's plan */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="sun"
              title="Today's plan"
              sub={`${TODAY.blocks.length} blocks · ${TODAY.blocks.filter((b) => b.done).length} done`}
              right={
                <button className="btn btn-sm btn-ghost" onClick={() => navigate('tasks')}>
                  All tasks <Icon name="chevron" size={13} />
                </button>
              }
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {TODAY.blocks.map((block, i) => (
                <PlanBlock key={i} block={block} />
              ))}
            </div>
          </div>

          {/* pending approvals */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="check"
              title="Pending approvals"
              sub="Batched — review, don't babysit"
              right={
                <div style={{ display: 'flex', gap: 'var(--s2)' }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => navigate('agent')}>
                    Review
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={() => navigate('agent')}>
                    Apply {APPROVALS.filter((a) => a.risk !== 'high').length} safe
                  </button>
                </div>
              }
            />
            <div>
              {APPROVALS.map((a) => (
                <ApprovalRow key={a.id} approval={a} />
              ))}
            </div>
          </div>

          {/* two-up: command output + recent AI work */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s5)' }}>

            {/* command output — live from backend */}
            <div className="panel panel-pad">
              <PanelHeader icon="cmd" title="Recent command output" />
              {cmdLog.length === 0 ? (
                <div
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--txt-3)', paddingTop: 'var(--s2)' }}
                >
                  No commands run yet. Use Quick actions or ⌘K.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                  {cmdLog.map((entry, i) => (
                    <div key={i} style={{ fontSize: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <StatusDot tone={entry.ok ? 'green' : 'red'} />
                        <span className="mono" style={{ color: 'var(--txt-0)', fontSize: 11.5 }}>
                          $ {entry.cmd}
                        </span>
                        <span className="mono" style={{ marginLeft: 'auto', color: 'var(--txt-3)', fontSize: 10.5 }}>
                          {entry.at}
                        </span>
                      </div>
                      <div
                        className="mono"
                        style={{
                          fontSize: 10.5,
                          color: 'var(--txt-2)',
                          paddingLeft: 14,
                          marginTop: 2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {entry.out}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* recent AI work */}
            <div className="panel panel-pad">
              <PanelHeader
                icon="merge"
                title="Recent AI work"
                right={
                  <button className="btn btn-sm btn-ghost" onClick={() => navigate('consolidate')}>
                    <Icon name="chevron" size={13} />
                  </button>
                }
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                {CONSOLIDATED.map((item) => (
                  <div key={item.id} style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
                    <SourceGlyph source={item.source} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 500,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          color: 'var(--txt-0)',
                        }}
                      >
                        {item.title}
                      </div>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--txt-2)' }}>
                        {item.dest}
                      </div>
                    </div>
                    <span style={{ fontSize: 10.5, color: 'var(--txt-3)', whiteSpace: 'nowrap' }}>
                      {item.when}
                    </span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* ── right rail ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

          {/* agent panel */}
          <div
            className="panel"
            style={{
              padding: 'var(--s5)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--s3)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
              }}
            >
              <span className="eyebrow">OpenClaw</span>
              <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} />
            </div>

            <div
              onClick={() => navigate('agent')}
              style={{ cursor: 'pointer' }}
              title="Open Local Agent"
            >
              <AgentSphere
                state={agentState}
                size={150}
                variant="orb"
                count={agentState === 'batch' ? 6 : undefined}
              />
            </div>

            <div style={{ textAlign: 'center' }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: meta?.tone === 'live' ? 'var(--live)' :
                         meta?.tone === 'amber' ? 'var(--amber)' :
                         meta?.tone === 'red' ? 'var(--red)' :
                         meta?.tone === 'violet' ? 'var(--violet)' :
                         meta?.tone === 'green' ? 'var(--green)' :
                         'var(--grey)',
                }}
              >
                {meta?.label ?? agentState}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>{meta?.blurb}</div>
            </div>

            <form
              onSubmit={submitAsk}
              style={{ width: '100%', display: 'flex', gap: 6, marginTop: 4 }}
            >
              <input
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
                placeholder="Ask the agent…"
                style={{
                  flex: 1,
                  background: 'var(--surface-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 'var(--r2)',
                  padding: '8px 11px',
                  color: 'var(--txt-0)',
                  fontSize: 13,
                  fontFamily: 'var(--font-ui)',
                  outline: 'none',
                }}
              />
              <button className="btn btn-primary" type="submit" style={{ padding: '0 11px' }}>
                <Icon name="enter" size={15} />
              </button>
            </form>
          </div>

          {/* runtime status */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="shield"
              title="Runtime status"
              right={
                <button className="btn btn-sm btn-ghost" onClick={() => navigate('safety')}>
                  <Icon name="chevron" size={13} />
                </button>
              }
            />
            {/* real: backend + brain CLI + local model (Ollama) */}
            <SystemRow service={backendService} />
            <SystemRow service={brainService} />
            <SystemRow service={localModelService} />
            {/* mocked: OpenClaw/NemoClaw/browser/computer/MCP */}
            {[SYSTEM.openclaw, SYSTEM.nemoclaw, SYSTEM.browser, SYSTEM.computer, SYSTEM.mcp].map(
              (svc, i) => <SystemRow key={i} service={svc} />
            )}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                marginTop: 'var(--s3)',
                color: 'var(--txt-2)',
              }}
            >
              <Icon name="folder" size={13} />
              <span
                className="mono"
                style={{
                  fontSize: 10.5,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {vaultDisplay}
              </span>
            </div>
          </div>

          {/* quick actions */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="bolt"
              title="Quick actions"
              right={<span className="kbd">⌘K</span>}
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 'var(--s2)',
              }}
            >
              {QUICK_ACTIONS.slice(0, 8).map((q) => (
                <button
                  key={q.id}
                  className="btn"
                  style={{ justifyContent: 'flex-start', fontSize: 12 }}
                  onClick={() => runCommand(q.id)}
                >
                  <Icon name={q.glyph} size={14} />
                  {q.label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
