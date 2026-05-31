/* ============================================================
   BRAIN UI — Local Agent cockpit
   ============================================================ */
(function () {
  const { Icon, AgentSphere, StatusDot, Pill, PanelHeader, RiskBadge, ConfidenceBadge, toneColor } = window;
  const { useState, useRef, useEffect } = React;

  const STATE_ORDER = ['idle','listening','thinking','speaking','researching','browser','computeruse','pending','batch','escalation','guarded','blocked','locked'];

  function ModeItem({ m, active, onClick }) {
    return React.createElement('button', {
      onClick, style: {
        textAlign: 'left', width: '100%', padding: '9px 11px', borderRadius: 'var(--r2)',
        background: active ? 'var(--live-bg)' : 'transparent',
        border: `1px solid ${active ? 'var(--live-line)' : 'transparent'}`,
        cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2,
        transition: 'background var(--fast)',
      },
      onMouseEnter: (e) => { if (!active) e.currentTarget.style.background = 'var(--surface-2)'; },
      onMouseLeave: (e) => { if (!active) e.currentTarget.style.background = 'transparent'; },
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7 } },
        React.createElement(StatusDot, { tone: active ? (m.id === 'locked' ? 'grey' : 'live') : 'grey', pulse: active && m.id !== 'locked' }),
        React.createElement('span', { style: { fontSize: 13, fontWeight: active ? 600 : 500, color: active ? 'var(--txt-0)' : 'var(--txt-1)' } }, m.label)),
      React.createElement('span', { style: { fontSize: 11, color: 'var(--txt-2)', paddingLeft: 14, lineHeight: 1.35 } }, m.desc),
    );
  }

  function Bubble({ m }) {
    const isUser = m.who === 'user';
    return React.createElement('div', {
      style: { display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', gap: 6 },
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, color: 'var(--txt-2)', fontSize: 11 } },
        !isUser && React.createElement(StatusDot, { tone: 'live' }),
        React.createElement('span', { className: 'eyebrow' }, isUser ? 'You' : 'OpenClaw')),
      React.createElement('div', {
        style: {
          maxWidth: '82%', padding: '11px 14px', borderRadius: 'var(--r3)', fontSize: 13.5, lineHeight: 1.5, whiteSpace: 'pre-wrap',
          background: isUser ? 'var(--surface-3)' : 'var(--surface)',
          border: `1px solid ${isUser ? 'var(--line)' : 'var(--live-line)'}`,
          color: 'var(--txt-0)',
          borderTopRightRadius: isUser ? 4 : 'var(--r3)', borderTopLeftRadius: isUser ? 'var(--r3)' : 4,
        },
      }, m.text),
      m.research && React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, color: 'var(--live)' } },
        React.createElement(Icon, { name: 'search', size: 13 }), 'Research run started · 10:00 budget'),
      m.proposals && React.createElement('div', { style: { display: 'flex', gap: 7, flexWrap: 'wrap' } },
        m.proposals.map((p, i) => React.createElement('button', { key: i, className: 'btn btn-sm', style: { background: 'var(--live-bg)', borderColor: 'var(--live-line)', color: 'var(--live)' } },
          React.createElement(Icon, { name: 'spark', size: 12 }), p))),
    );
  }

  function ToolRequest({ onApprove, onDeny }) {
    return React.createElement('div', { className: 'panel', style: { padding: 'var(--s4)', borderColor: 'var(--amber-line)', background: 'var(--amber-bg)' } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 } },
        React.createElement(Icon, { name: 'shield', size: 14, style: { color: 'var(--amber)' } }),
        React.createElement('span', { style: { fontSize: 12.5, fontWeight: 600, color: 'var(--amber)' } }, 'Tool request'),
        React.createElement('span', { style: { marginLeft: 'auto' } }, React.createElement(RiskBadge, { level: 'medium', compact: true }))),
      React.createElement('div', { style: { fontSize: 12.5, marginBottom: 6 } }, 'Write research packet → ',
        React.createElement('span', { className: 'mono', style: { color: 'var(--txt-1)' } }, 'wiki/research/NemoClaw.md')),
      React.createElement('div', { style: { fontSize: 11.5, color: 'var(--txt-2)', marginBottom: 10 } }, 'Routed through NemoClaw/OpenShell → backend gateway. Reversible vault write.'),
      React.createElement('div', { style: { display: 'flex', gap: 7 } },
        React.createElement('button', { className: 'btn btn-sm', style: { flex: 1, justifyContent: 'center', background: 'var(--amber)', color: 'var(--bg-0)', borderColor: 'transparent', fontWeight: 600 }, onClick: onApprove }, 'Approve'),
        React.createElement('button', { className: 'btn btn-sm', style: { flex: 1, justifyContent: 'center' }, onClick: onDeny }, 'Reject')));
  }

  function ResearchMini() {
    const r = window.RESEARCH;
    const pct = Math.round((r.elapsed / r.budget) * 100);
    return React.createElement('div', { className: 'panel panel-pad' },
      React.createElement(PanelHeader, { icon: 'search', title: 'Research run',
        right: React.createElement(Pill, { tone: 'live' }, r.elapsed.toFixed(1) + ' / ' + r.budget + 'm') }),
      React.createElement('div', { style: { fontSize: 12.5, marginBottom: 10, color: 'var(--txt-1)' } }, r.query),
      React.createElement('div', { style: { height: 5, borderRadius: 3, background: 'var(--surface-3)', overflow: 'hidden', marginBottom: 12 } },
        React.createElement('div', { style: { width: pct + '%', height: '100%', background: 'var(--live)', borderRadius: 3 } })),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 } },
        [['Sources', r.sources.length], ['Claims', r.claims], ['Confidence', r.confidence], ['Depth', r.depth]].map(([k, v], i) =>
          React.createElement('div', { key: i, style: { background: 'var(--surface-2)', borderRadius: 'var(--r2)', padding: '7px 10px' } },
            React.createElement('div', { className: 'eyebrow', style: { fontSize: 9.5 } }, k),
            React.createElement('div', { style: { fontSize: 13, fontWeight: 600, marginTop: 1 } }, v)))),
      React.createElement('div', { style: { fontSize: 11, color: 'var(--txt-2)', marginBottom: 6 } }, 'Sources'),
      r.sources.map((s, i) => React.createElement('div', { key: i, style: { display: 'flex', gap: 7, alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--line-soft)' } },
        React.createElement(Icon, { name: 'globe', size: 12, style: { color: 'var(--txt-3)', flex: '0 0 auto' } }),
        React.createElement('span', { style: { fontSize: 11.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 } }, s.title),
        React.createElement('span', { style: { fontSize: 10, color: 'var(--txt-3)' } }, s.when))),
      React.createElement('div', { style: { marginTop: 12, padding: '9px 11px', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)' } },
        React.createElement('div', { style: { fontSize: 11, color: 'var(--amber)', fontWeight: 600, marginBottom: 3 } }, 'Not yet checked'),
        r.gaps.map((g, i) => React.createElement('div', { key: i, style: { fontSize: 11, color: 'var(--txt-1)' } }, '· ' + g))),
      React.createElement('div', { style: { display: 'flex', gap: 7, marginTop: 12 } },
        React.createElement('button', { className: 'btn btn-sm', style: { flex: 1, justifyContent: 'center' } }, React.createElement(Icon, { name: 'arrow-up', size: 13 }), 'Escalate'),
        React.createElement('button', { className: 'btn btn-sm btn-primary', style: { flex: 1, justifyContent: 'center' } }, 'Save to vault')));
  }

  function LocalAgent({ agentState, setAgentState, mode, setMode, modes, conversation, onSend, onNavigate }) {
    const [draft, setDraft] = useState('');
    const scrollRef = useRef(null);
    const meta = window.AGENT_STATES[agentState] || {};
    useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [conversation]);
    const send = (e) => { e.preventDefault(); if (draft.trim()) { onSend(draft.trim()); setDraft(''); } };

    return React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '244px minmax(0,1fr) 332px', gap: 'var(--s4)', height: '100%', maxWidth: 1480, margin: '0 auto' } },

      // ---- left: modes + context ----
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s4)', minHeight: 0 } },
        React.createElement('div', { className: 'panel panel-pad', style: { flex: '0 0 auto' } },
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 10 } }, 'Agent mode'),
          React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 2 } },
            modes.map((m) => React.createElement(ModeItem, { key: m.id, m, active: mode.id === m.id, onClick: () => setMode(m) })))),
        React.createElement('div', { className: 'panel panel-pad', style: { flex: 1, minHeight: 0, overflow: 'auto' } },
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 10 } }, 'Current context'),
          [['Active project', 'Brain UI'], ['Active course', 'MAT292'], ['Vault', 'AI-Command-Center'], ['Model', 'qwen2.5:14b']].map(([k, v], i) =>
            React.createElement('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--line-soft)', fontSize: 12 } },
              React.createElement('span', { style: { color: 'var(--txt-2)' } }, k),
              React.createElement('span', { className: 'mono', style: { fontSize: 11, color: 'var(--txt-1)' } }, v))),
          React.createElement('div', { className: 'eyebrow', style: { margin: '14px 0 8px' } }, 'Memory used'),
          ['standup-2026-05-30.md', 'projects/Brain UI.md', 'ops/escalation-queue.md'].map((m, i) =>
            React.createElement('div', { key: i, style: { display: 'flex', gap: 6, alignItems: 'center', padding: '4px 0' } },
              React.createElement(Icon, { name: 'file', size: 11, style: { color: 'var(--txt-3)' } }),
              React.createElement('span', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)' } }, m))),
        ),
      ),

      // ---- center: sphere + conversation ----
      React.createElement('div', { className: 'panel', style: { display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' } },
        // cockpit head
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 'var(--s4)', padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line)' } },
          React.createElement(AgentSphere, { state: agentState, size: 64, variant: window.__sphereVariant || 'orb', count: agentState === 'batch' ? 6 : undefined }),
          React.createElement('div', { style: { flex: 1 } },
            React.createElement('div', { style: { fontSize: 15, fontWeight: 600, color: toneColor(meta.tone) } }, meta.label),
            React.createElement('div', { style: { fontSize: 12, color: 'var(--txt-2)' } }, meta.blurb)),
          React.createElement('button', { className: 'btn btn-sm', onClick: () => setAgentState('locked'), style: agentState === 'locked' ? { background: 'var(--surface-3)' } : null },
            React.createElement(Icon, { name: 'stop', size: 13 }), agentState === 'locked' ? 'Tools off' : 'Disable tools')),

        // state simulator (this is the live agent state surface)
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, padding: '8px var(--s5)', borderBottom: '1px solid var(--line-soft)', overflowX: 'auto', background: 'var(--bg-1)' } },
          React.createElement('span', { className: 'eyebrow', style: { flex: '0 0 auto' } }, 'State'),
          STATE_ORDER.map((s) => React.createElement('button', {
            key: s, onClick: () => setAgentState(s), title: window.AGENT_STATES[s].label,
            className: 'btn btn-sm', style: {
              padding: '3px 8px', fontSize: 11, flex: '0 0 auto',
              background: agentState === s ? 'var(--live-bg)' : 'transparent',
              borderColor: agentState === s ? 'var(--live-line)' : 'var(--line)',
              color: agentState === s ? 'var(--live)' : 'var(--txt-2)',
            },
          }, window.AGENT_STATES[s].label))),

        // transcript
        React.createElement('div', { ref: scrollRef, style: { flex: 1, overflowY: 'auto', padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' } },
          conversation.map((m, i) => React.createElement(Bubble, { key: i, m }))),

        // input
        React.createElement('form', { onSubmit: send, style: { padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' } },
          React.createElement('div', { style: { display: 'flex', gap: 7, flexWrap: 'wrap' } },
            [['Create proposal', 'spark'], ['Research', 'search'], ['Consolidate', 'merge'], ['Escalate', 'arrow-up']].map(([l, g], i) =>
              React.createElement('button', { key: i, type: 'button', className: 'btn btn-sm', style: { fontSize: 11.5 },
                onClick: () => l === 'Research' ? onNavigate('research') : l === 'Consolidate' ? onNavigate('consolidate') : l === 'Escalate' ? onNavigate('escalation') : null },
                React.createElement(Icon, { name: g, size: 13 }), l))),
          React.createElement('div', { style: { display: 'flex', gap: 'var(--s2)', alignItems: 'flex-end' } },
            React.createElement('textarea', {
              value: draft, onChange: (e) => setDraft(e.target.value), rows: 1, placeholder: 'Message OpenClaw…  (low-risk runs automatically · risky actions ask first)',
              onKeyDown: (e) => { if (e.key === 'Enter' && !e.shiftKey) send(e); },
              style: { flex: 1, resize: 'none', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', padding: '10px 13px', color: 'var(--txt-0)', fontSize: 13.5, fontFamily: 'var(--font-ui)', lineHeight: 1.4, maxHeight: 120 },
            }),
            React.createElement('button', { className: 'btn btn-primary', type: 'submit', style: { padding: '10px 13px' } }, React.createElement(Icon, { name: 'enter', size: 16 })))),
      ),

      // ---- right: tool requests + research ----
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s4)', minHeight: 0, overflowY: 'auto' } },
        (agentState === 'pending') && React.createElement(ToolRequest, { onApprove: () => setAgentState('guarded'), onDeny: () => setAgentState('idle') }),
        React.createElement(ResearchMini, null),
      ),
    );
  }

  window.LocalAgent = LocalAgent;
})();
