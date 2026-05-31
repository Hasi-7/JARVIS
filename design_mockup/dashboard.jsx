/* ============================================================
   BRAIN UI — Dashboard (daily operating view)
   ============================================================ */
(function () {
  const { Icon, StatusCard, StatusDot, Pill, PanelHeader, ConfidenceBadge,
          RiskBadge, AgentSphere, SourceGlyph, TagChip, ModeBadge, toneColor } = window;
  const { useState } = React;

  const STATE_DOT = { ready: 'green', idle: 'live', partial: 'amber', disabled: 'grey', blocked: 'red' };

  function SystemRow({ s }) {
    const tone = STATE_DOT[s.state] || 'grey';
    return React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '8px 0', borderBottom: '1px solid var(--line-soft)' },
    },
      React.createElement(StatusDot, { tone, pulse: s.state === 'idle' || s.state === 'ready' }),
      React.createElement('div', { style: { flex: 1, minWidth: 0 } },
        React.createElement('div', { style: { fontSize: 12.5, fontWeight: 500 } }, s.label),
        React.createElement('div', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, s.detail),
      ),
      React.createElement('span', { style: { fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: toneColor(tone) } }, s.state),
    );
  }

  function PlanBlock({ b }) {
    return React.createElement('div', {
      style: {
        display: 'grid', gridTemplateColumns: '54px 1fr auto', alignItems: 'center', gap: 'var(--s3)',
        padding: '9px 12px', borderRadius: 'var(--r2)',
        background: b.now ? 'var(--live-bg)' : 'transparent',
        border: `1px solid ${b.now ? 'var(--live-line)' : 'transparent'}`,
        opacity: b.done ? 0.55 : 1,
      },
    },
      React.createElement('div', { className: 'mono', style: { fontSize: 12, color: b.now ? 'var(--live)' : 'var(--txt-2)', fontWeight: 600 } }, b.time),
      React.createElement('div', { style: { minWidth: 0 } },
        React.createElement('div', { style: { fontSize: 13, fontWeight: 500, textDecoration: b.done ? 'line-through' : 'none', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, b.title),
        React.createElement('div', { style: { display: 'flex', gap: 8, alignItems: 'center', marginTop: 3 } },
          React.createElement(TagChip, { domain: b.tag }),
          React.createElement('span', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-3)' } }, b.dur),
          b.now && React.createElement(Pill, { tone: 'live' }, 'In progress'),
        ),
      ),
      b.done
        ? React.createElement('span', { style: { color: 'var(--green)' } }, React.createElement(Icon, { name: 'check', size: 15 }))
        : React.createElement('span', { style: { width: 15, height: 15, borderRadius: '50%', border: '1.5px solid var(--line-strong)' } }),
    );
  }

  function ApprovalRow({ a, onOpen }) {
    return React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '10px 0', borderBottom: '1px solid var(--line-soft)' },
    },
      React.createElement('div', { style: { flex: 1, minWidth: 0 } },
        React.createElement('div', { style: { fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, a.title),
        React.createElement('div', { style: { fontSize: 11, color: 'var(--txt-2)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, a.reason),
      ),
      React.createElement(ConfidenceBadge, { level: a.conf }),
      React.createElement(RiskBadge, { level: a.risk, compact: true }),
    );
  }

  function Dashboard({ agentState, mode, modes, onSelectMode, onNavigate, onAsk, onCommand, onCycleState }) {
    const [ask, setAsk] = useState('');
    const meta = window.AGENT_STATES[agentState] || {};
    const submit = (e) => { e.preventDefault(); if (ask.trim()) { onAsk(ask.trim()); setAsk(''); } };

    const counts = [
      { label: 'Approvals', value: window.APPROVALS.length, sub: '2 medium-risk', tone: 'amber', icon: 'check', nav: 'agent', accent: true },
      { label: 'Raw pending', value: 7, sub: '2 need review', tone: 'live', icon: 'inbox', nav: 'inbox' },
      { label: 'Escalations', value: window.ESCALATIONS.length, sub: '1 in progress', tone: 'violet', icon: 'arrow-up', nav: 'escalation' },
      { label: 'Calendar', value: 3, sub: 'candidates', tone: 'live', icon: 'cal', nav: 'calendar' },
      { label: 'Backfill', value: '34%', sub: '11 / 32 repos', icon: 'layers', nav: 'backfill' },
      { label: 'Resume', value: 6, sub: 'evidence rows', icon: 'doc', nav: 'resume' },
    ];

    return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s5)', maxWidth: 1320, margin: '0 auto' } },
      // header strip
      React.createElement('div', { style: { display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--s4)', flexWrap: 'wrap' } },
        React.createElement('div', null,
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 4 } }, window.TODAY.date + ' · Good afternoon, Hasnain'),
          React.createElement('h1', { style: { margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: '-0.015em' } }, 'Today\'s focus'),
          React.createElement('div', { style: { fontSize: 14, color: 'var(--txt-1)', marginTop: 2 } }, window.TODAY.focus),
        ),
        React.createElement('div', { style: { display: 'flex', gap: 'var(--s2)' } },
          React.createElement('button', { className: 'btn', onClick: () => onCommand('today') }, React.createElement(Icon, { name: 'sun', size: 15 }), 'Run today'),
          React.createElement('button', { className: 'btn', onClick: () => onCommand('weekly') }, React.createElement(Icon, { name: 'cal', size: 15 }), 'Weekly'),
          React.createElement('button', { className: 'btn btn-primary', onClick: () => onNavigate('inbox') }, React.createElement(Icon, { name: 'upload', size: 15 }), 'Upload raw'),
        ),
      ),

      // count strip
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--s3)' } },
        counts.map((c) => React.createElement(StatusCard, { key: c.label, ...c, dot: !!c.tone, onClick: () => onNavigate(c.nav) }))),

      // main grid
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0,1.9fr) minmax(320px,1fr)', gap: 'var(--s5)', alignItems: 'start' } },

        // ---- main column ----
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s5)' } },
          // today plan
          React.createElement('div', { className: 'panel panel-pad' },
            React.createElement(PanelHeader, { icon: 'sun', title: 'Today\'s plan', sub: '5 blocks · 2 done',
              right: React.createElement('button', { className: 'btn btn-sm btn-ghost', onClick: () => onNavigate('tasks') }, 'All tasks', React.createElement(Icon, { name: 'chevron', size: 13 })) }),
            React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 2 } },
              window.TODAY.blocks.map((b, i) => React.createElement(PlanBlock, { key: i, b })))),

          // approvals
          React.createElement('div', { className: 'panel panel-pad' },
            React.createElement(PanelHeader, { icon: 'check', title: 'Pending approvals',
              sub: 'Batched — review, don\'t babysit',
              right: React.createElement('div', { style: { display: 'flex', gap: 'var(--s2)' } },
                React.createElement('button', { className: 'btn btn-sm btn-ghost', onClick: () => onNavigate('agent') }, 'Review'),
                React.createElement('button', { className: 'btn btn-sm btn-primary', onClick: () => onNavigate('agent') }, 'Apply 4 safe')) }),
            React.createElement('div', null, window.APPROVALS.map((a) => React.createElement(ApprovalRow, { key: a.id, a })))),

          // two-up
          React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s5)' } },
            // command output
            React.createElement('div', { className: 'panel panel-pad' },
              React.createElement(PanelHeader, { icon: 'cmd', title: 'Recent command output' }),
              React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s3)' } },
                window.CMD_LOG.map((c, i) => React.createElement('div', { key: i, style: { fontSize: 12 } },
                  React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7 } },
                    React.createElement(StatusDot, { tone: c.ok ? 'green' : 'red' }),
                    React.createElement('span', { className: 'mono', style: { color: 'var(--txt-0)', fontSize: 11.5 } }, '$ ' + c.cmd),
                    React.createElement('span', { className: 'mono', style: { marginLeft: 'auto', color: 'var(--txt-3)', fontSize: 10.5 } }, c.at)),
                  React.createElement('div', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)', paddingLeft: 14, marginTop: 2 } }, c.out))))),
            // consolidated work
            React.createElement('div', { className: 'panel panel-pad' },
              React.createElement(PanelHeader, { icon: 'merge', title: 'Recent AI work',
                right: React.createElement('button', { className: 'btn btn-sm btn-ghost', onClick: () => onNavigate('consolidate') }, React.createElement(Icon, { name: 'chevron', size: 13 })) }),
              React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s3)' } },
                window.CONSOLIDATED.map((c) => React.createElement('div', { key: c.id, style: { display: 'flex', gap: 9, alignItems: 'center' } },
                  React.createElement(SourceGlyph, { source: c.source }),
                  React.createElement('div', { style: { minWidth: 0, flex: 1 } },
                    React.createElement('div', { style: { fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, c.title),
                    React.createElement('div', { className: 'mono', style: { fontSize: 10, color: 'var(--txt-2)' } }, c.dest)),
                  React.createElement('span', { style: { fontSize: 10.5, color: 'var(--txt-3)', whiteSpace: 'nowrap' } }, c.when)))))),
        ),

        // ---- right rail ----
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s5)' } },
          // agent panel
          React.createElement('div', { className: 'panel', style: { padding: 'var(--s5)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--s3)' } },
            React.createElement('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' } },
              React.createElement('span', { className: 'eyebrow' }, 'OpenClaw'),
              React.createElement(ModeBadge, { mode, modes, onSelect: onSelectMode })),
            React.createElement('div', { onClick: onCycleState, style: { cursor: 'pointer' }, title: 'Demo: cycle agent state' },
              React.createElement(AgentSphere, { state: agentState, size: 150, variant: window.__sphereVariant || 'orb', count: agentState === 'batch' ? 6 : undefined })),
            React.createElement('div', { style: { textAlign: 'center' } },
              React.createElement('div', { style: { fontSize: 14, fontWeight: 600, color: toneColor(meta.tone) } }, meta.label),
              React.createElement('div', { style: { fontSize: 11.5, color: 'var(--txt-2)' } }, meta.blurb)),
            React.createElement('form', { onSubmit: submit, style: { width: '100%', display: 'flex', gap: 6, marginTop: 4 } },
              React.createElement('input', {
                value: ask, onChange: (e) => setAsk(e.target.value), placeholder: 'Ask the agent…',
                style: { flex: 1, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', padding: '8px 11px', color: 'var(--txt-0)', fontSize: 13, fontFamily: 'var(--font-ui)' },
              }),
              React.createElement('button', { className: 'btn btn-primary', type: 'submit', style: { padding: '0 11px' } }, React.createElement(Icon, { name: 'enter', size: 15 }))),
          ),

          // system status
          React.createElement('div', { className: 'panel panel-pad' },
            React.createElement(PanelHeader, { icon: 'shield', title: 'Runtime status',
              right: React.createElement('button', { className: 'btn btn-sm btn-ghost', onClick: () => onNavigate('safety') }, React.createElement(Icon, { name: 'chevron', size: 13 })) }),
            [window.SYSTEM.openclaw, window.SYSTEM.nemoclaw, window.SYSTEM.browser, window.SYSTEM.computer, window.SYSTEM.mcp].map((s, i) =>
              React.createElement(SystemRow, { key: i, s })),
            React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, marginTop: 'var(--s3)', color: 'var(--txt-2)' } },
              React.createElement(Icon, { name: 'folder', size: 13 }),
              React.createElement('span', { className: 'mono', style: { fontSize: 10.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, window.SYSTEM.vault))),

          // quick actions
          React.createElement('div', { className: 'panel panel-pad' },
            React.createElement(PanelHeader, { icon: 'bolt', title: 'Quick actions',
              right: React.createElement('span', { className: 'kbd' }, '⌘K') }),
            React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s2)' } },
              window.QUICK_ACTIONS.slice(0, 8).map((q) => React.createElement('button', {
                key: q.id, className: 'btn', style: { justifyContent: 'flex-start', fontSize: 12 },
                onClick: () => q.cmd ? onCommand(q.id) : (q.id === 'ask' ? onNavigate('agent') : q.id === 'research' ? onNavigate('research') : q.id === 'consolidate' ? onNavigate('consolidate') : q.id === 'upload' ? onNavigate('inbox') : onCommand(q.id)),
              }, React.createElement(Icon, { name: q.glyph, size: 14 }), q.label)))),
        ),
      ),
    );
  }

  window.Dashboard = Dashboard;
})();
