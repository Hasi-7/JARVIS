/* ============================================================
   BRAIN UI — app shell (sidebar · command bar · ⌘K · tweaks)
   ============================================================ */
const { useState, useEffect, useRef, useMemo } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "azure",
  "temp": "cool",
  "density": "comfortable",
  "sphere": "orb",
  "fontPair": "grotesk"
}/*EDITMODE-END*/;

const ACCENT_HUE = { cyan: 198, azure: 230, indigo: 268, teal: 178 };
const TEMP = { cool: { h: 258, c: 0.008 }, neutral: { h: 286, c: 0.005 }, warm: { h: 74, c: 0.007 } };
const DENSITY = { compact: 0.86, comfortable: 1 };
const FONTS = {
  grotesk: { ui: "'Schibsted Grotesk', system-ui, sans-serif", mono: "'JetBrains Mono', monospace" },
  hanken:  { ui: "'Hanken Grotesk', system-ui, sans-serif", mono: "'IBM Plex Mono', monospace" },
  archivo: { ui: "'Archivo', system-ui, sans-serif", mono: "'Space Mono', monospace" },
};

// ---------- Sidebar ----------
function Sidebar({ route, onNavigate, agentState }) {
  const { Icon } = window;
  return (
    React.createElement('aside', { style: { width: 220, flex: '0 0 auto', background: 'var(--bg-1)', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', height: '100%' } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '16px 18px 14px' } },
        React.createElement(window.AgentSphere, { state: agentState, size: 30, variant: 'minimal' }),
        React.createElement('div', null,
          React.createElement('div', { style: { fontSize: 14, fontWeight: 700, letterSpacing: '-0.01em' } }, 'BRAIN UI'),
          React.createElement('div', { className: 'mono', style: { fontSize: 9.5, color: 'var(--txt-3)', letterSpacing: '0.04em' } }, 'COMMAND CENTER'))),
      React.createElement('hr', { className: 'hairline' }),
      React.createElement('nav', { style: { flex: 1, overflowY: 'auto', padding: '12px 10px' } },
        window.NAV.map((g) => React.createElement('div', { key: g.group, style: { marginBottom: 14 } },
          React.createElement('div', { className: 'eyebrow', style: { padding: '0 8px 6px', fontSize: 9.5 } }, g.group),
          g.items.map((it) => {
            const active = route === it.id;
            return React.createElement('button', {
              key: it.id, onClick: () => onNavigate(it.id),
              style: {
                width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '7px 8px', borderRadius: 'var(--r2)',
                border: '1px solid transparent', cursor: 'pointer', marginBottom: 1, fontSize: 13,
                background: active ? 'var(--surface-2)' : 'transparent',
                color: active ? 'var(--txt-0)' : 'var(--txt-1)',
                borderColor: active ? 'var(--line)' : 'transparent',
                fontWeight: active ? 600 : 500,
                position: 'relative',
              },
              onMouseEnter: (e) => { if (!active) e.currentTarget.style.background = 'var(--surface)'; },
              onMouseLeave: (e) => { if (!active) e.currentTarget.style.background = 'transparent'; },
            },
              active && React.createElement('span', { style: { position: 'absolute', left: -10, top: 8, bottom: 8, width: 2, background: 'var(--live)', borderRadius: 2 } }),
              React.createElement('span', { style: { color: active ? 'var(--live)' : 'var(--txt-2)', display: 'flex' } }, React.createElement(Icon, { name: it.glyph, size: 16 })),
              React.createElement('span', { style: { flex: 1, textAlign: 'left' } }, it.label),
              it.badge && React.createElement('span', { style: { fontSize: 10.5, fontWeight: 700, fontFamily: 'var(--font-mono)', minWidth: 18, height: 18, padding: '0 5px', borderRadius: 9, background: active ? 'var(--live-bg)' : 'var(--surface-3)', color: active ? 'var(--live)' : 'var(--txt-2)', display: 'grid', placeItems: 'center' } }, it.badge),
            );
          }),
        ))),
      React.createElement('hr', { className: 'hairline' }),
      React.createElement('div', { style: { padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8 } },
        React.createElement(window.StatusDot, { tone: 'green', pulse: true }),
        React.createElement('span', { style: { fontSize: 11, color: 'var(--txt-2)' } }, 'Vault synced'),
        React.createElement('span', { className: 'mono', style: { marginLeft: 'auto', fontSize: 10, color: 'var(--txt-3)' } }, 'v0.1')),
    )
  );
}

// ---------- Top command bar ----------
function TopBar({ title, mode, modes, onSelectMode, agentState, onOpenPalette, onNavigate }) {
  const { Icon, ModeBadge, StatusDot } = window;
  const sys = window.SYSTEM;
  const pills = [['OpenClaw', sys.openclaw.state], ['NemoClaw', sys.nemoclaw.state], ['Browser', sys.browser.state], ['CompUse', sys.computer.state]];
  const tone = { ready: 'green', idle: 'live', partial: 'amber', disabled: 'grey', blocked: 'red' };
  return (
    React.createElement('header', { style: { height: 56, flex: '0 0 auto', borderBottom: '1px solid var(--line)', background: 'var(--bg-1)', display: 'flex', alignItems: 'center', gap: 'var(--s4)', padding: '0 var(--s5)' } },
      React.createElement('div', { style: { fontSize: 14, fontWeight: 600, minWidth: 120 } }, title),
      React.createElement('button', {
        onClick: onOpenPalette,
        style: { flex: 1, maxWidth: 460, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderRadius: 'var(--r2)', background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--txt-2)', cursor: 'pointer', fontSize: 13 },
      },
        React.createElement(Icon, { name: 'search', size: 14 }),
        React.createElement('span', { style: { flex: 1, textAlign: 'left' } }, 'Search, run a command, jump anywhere…'),
        React.createElement('span', { className: 'kbd' }, '⌘K')),
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        React.createElement('div', { style: { display: 'flex', gap: 10, paddingRight: 6, borderRight: '1px solid var(--line)', marginRight: 4 } },
          pills.map(([l, s]) => React.createElement('span', { key: l, title: l + ' · ' + s, style: { display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--txt-2)' } },
            React.createElement(StatusDot, { tone: tone[s], pulse: s === 'ready' }), l))),
        React.createElement(ModeBadge, { mode, modes, onSelect: onSelectMode })),
    )
  );
}

// ---------- Command palette ----------
function CommandPalette({ open, onClose, onNavigate, onCommand }) {
  const { Icon } = window;
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef(null);
  useEffect(() => { if (open) { setQ(''); setSel(0); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);

  const items = useMemo(() => {
    const nav = window.NAV.flatMap((g) => g.items.map((it) => ({ kind: 'nav', id: it.id, label: it.label, group: 'Go to', glyph: it.glyph })));
    const acts = window.QUICK_ACTIONS.map((a) => ({ kind: a.cmd ? 'cmd' : 'act', id: a.id, label: a.label, group: a.cmd ? 'Run · ' + a.cmd : 'Action', glyph: a.glyph }));
    return [...acts, ...nav];
  }, []);
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? items.filter((i) => (i.label + i.group).toLowerCase().includes(s)) : items;
  }, [q, items]);
  useEffect(() => { setSel(0); }, [q]);

  if (!open) return null;
  const run = (it) => { onClose(); if (it.kind === 'nav') onNavigate(it.id); else onCommand(it.id); };
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (filtered[sel]) run(filtered[sel]); }
    else if (e.key === 'Escape') { onClose(); }
  };
  return (
    React.createElement('div', {
      onClick: onClose,
      style: { position: 'fixed', inset: 0, background: 'rgb(0 0 0 / 0.5)', backdropFilter: 'blur(3px)', zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh' },
    },
      React.createElement('div', {
        onClick: (e) => e.stopPropagation(),
        style: { width: 'min(620px, 92vw)', background: 'var(--surface)', border: '1px solid var(--line-strong)', borderRadius: 'var(--r4)', boxShadow: 'var(--shadow-pop)', overflow: 'hidden' },
      },
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', borderBottom: '1px solid var(--line)' } },
          React.createElement(Icon, { name: 'cmd', size: 17, style: { color: 'var(--live)' } }),
          React.createElement('input', {
            ref: inputRef, value: q, onChange: (e) => setQ(e.target.value), onKeyDown: onKey,
            placeholder: 'Type a command or search…',
            style: { flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--txt-0)', fontSize: 15, fontFamily: 'var(--font-ui)' },
          }),
          React.createElement('span', { className: 'kbd' }, 'esc')),
        React.createElement('div', { style: { maxHeight: 360, overflowY: 'auto', padding: 8 } },
          filtered.length === 0
            ? React.createElement('div', { style: { padding: 24, textAlign: 'center', color: 'var(--txt-2)', fontSize: 13 } }, 'No matches')
            : filtered.map((it, i) => React.createElement('button', {
                key: it.kind + it.id, onMouseEnter: () => setSel(i), onClick: () => run(it),
                style: {
                  width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 'var(--r2)',
                  border: 'none', cursor: 'pointer', textAlign: 'left',
                  background: sel === i ? 'var(--surface-3)' : 'transparent', color: 'var(--txt-0)',
                },
              },
                React.createElement('span', { style: { color: sel === i ? 'var(--live)' : 'var(--txt-2)', display: 'flex' } }, React.createElement(Icon, { name: it.glyph, size: 16 })),
                React.createElement('span', { style: { flex: 1, fontSize: 13.5 } }, it.label),
                React.createElement('span', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-3)' } }, it.group),
                sel === i && React.createElement(Icon, { name: 'enter', size: 14, style: { color: 'var(--txt-2)' } }),
              ))),
      )
    )
  );
}

// ---------- Toast ----------
function Toast({ msg }) {
  if (!msg) return null;
  const { Icon } = window;
  return React.createElement('div', {
    style: { position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 300, display: 'flex', alignItems: 'center', gap: 9, padding: '10px 16px', background: 'var(--surface-2)', border: '1px solid var(--live-line)', borderRadius: 'var(--r-pill)', boxShadow: 'var(--shadow-2)', fontSize: 13 },
  }, React.createElement(Icon, { name: 'check', size: 15, style: { color: 'var(--live)' } }), msg);
}

// ---------- App ----------
function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [route, setRoute] = useState('dashboard');
  const [agentState, setAgentState] = useState('idle');
  const [mode, setMode] = useState(window.AGENT_MODES[3]); // Assist
  const [conversation, setConversation] = useState(window.CONVERSATION);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [toast, setToast] = useState('');
  const toastTimer = useRef(null);
  const speakTimer = useRef(null);

  // apply tweaks to :root
  useEffect(() => {
    const root = document.documentElement.style;
    root.setProperty('--accent-h', ACCENT_HUE[t.accent] ?? 230);
    root.setProperty('--base-h', TEMP[t.temp]?.h ?? 258);
    root.setProperty('--base-c', TEMP[t.temp]?.c ?? 0.008);
    root.setProperty('--density', DENSITY[t.density] ?? 1);
    root.setProperty('--font-ui', FONTS[t.fontPair]?.ui);
    root.setProperty('--font-mono', FONTS[t.fontPair]?.mono);
    window.__sphereVariant = t.sphere;
  }, [t]);

  // ⌘K
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen((o) => !o); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const showToast = (m) => { setToast(m); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(''), 2200); };

  const runCommand = (id) => {
    const a = window.QUICK_ACTIONS.find((x) => x.id === id);
    if (a?.cmd) { showToast('Ran ' + a.cmd); setAgentState('thinking'); clearTimeout(speakTimer.current); speakTimer.current = setTimeout(() => setAgentState('idle'), 1400); }
    else if (id === 'ask') { setRoute('agent'); }
    else if (id === 'research') { setRoute('research'); }
    else if (id === 'consolidate') { setRoute('consolidate'); }
    else if (id === 'upload') { setRoute('inbox'); }
    else showToast('Opened ' + (a?.label || id));
  };

  const ask = (text) => {
    setRoute('agent');
    setConversation((c) => [...c, { who: 'user', text }]);
    setAgentState('thinking');
    clearTimeout(speakTimer.current);
    speakTimer.current = setTimeout(() => {
      setAgentState('speaking');
      const research = /research/i.test(text);
      setConversation((c) => [...c, research
        ? { who: 'agent', text: 'Starting a time-boxed research run. I\'ll capture sources, extract claims, label confidence, and bring back a save-to-Obsidian proposal — nothing is written until you approve.', research: true }
        : { who: 'agent', text: 'On it. I\'ve pulled the relevant vault context and drafted a response. Low-risk steps ran automatically; anything that touches your files or calendar is queued for your approval.', proposals: ['Review queued changes', 'Open related project'] }]);
      if (research) setTimeout(() => setAgentState('researching'), 900);
      else setTimeout(() => setAgentState('idle'), 2600);
    }, 1500);
  };

  const cycleState = () => {
    const order = ['idle', 'listening', 'thinking', 'speaking', 'researching', 'pending', 'batch', 'escalation', 'blocked', 'guarded', 'locked'];
    setAgentState((s) => order[(order.indexOf(s) + 1) % order.length]);
  };
  const cycleMode = () => {
    const i = window.AGENT_MODES.findIndex((m) => m.id === mode.id);
    setMode(window.AGENT_MODES[(i + 1) % window.AGENT_MODES.length]);
  };

  const title = (window.NAV.flatMap((g) => g.items).find((i) => i.id === route) || {}).label || 'Brain UI';

  let screen;
  if (route === 'dashboard') screen = React.createElement(window.Dashboard, { agentState, mode, modes: window.AGENT_MODES, onSelectMode: setMode, onNavigate: setRoute, onAsk: ask, onCommand: runCommand, onCycleState: cycleState });
  else if (route === 'agent') screen = React.createElement(window.LocalAgent, { agentState, setAgentState, mode, setMode, modes: window.AGENT_MODES, conversation, onSend: ask, onNavigate: setRoute });
  else if (route === 'inbox') screen = React.createElement(window.RawInbox, null);
  else if (window.SCREENS_EXTRA[route]) screen = React.createElement(window.SCREENS_EXTRA[route], null);
  else screen = React.createElement('div', { style: { color: 'var(--txt-2)' } }, 'Not found');

  const scroll = route === 'agent';

  return (
    React.createElement('div', { style: { display: 'flex', height: '100vh', overflow: 'hidden' } },
      React.createElement(Sidebar, { route, onNavigate: setRoute, agentState }),
      React.createElement('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 } },
        React.createElement(TopBar, { title, mode, modes: window.AGENT_MODES, onSelectMode: setMode, agentState, onOpenPalette: () => setPaletteOpen(true), onNavigate: setRoute }),
        React.createElement('main', { style: { flex: 1, overflowY: scroll ? 'hidden' : 'auto', padding: scroll ? 'var(--s5)' : 'var(--s6) var(--s6)', minHeight: 0 } }, screen)),
      React.createElement(CommandPalette, { open: paletteOpen, onClose: () => setPaletteOpen(false), onNavigate: setRoute, onCommand: runCommand }),
      React.createElement(Toast, { msg: toast }),
      // ---- Tweaks ----
      React.createElement(TweaksPanel, { title: 'Tweaks' },
        React.createElement(TweakSection, { label: 'Color' }),
        React.createElement(TweakSelect, { label: 'Accent', value: t.accent, options: ['cyan', 'azure', 'indigo', 'teal'], onChange: (v) => setTweak('accent', v) }),
        React.createElement(TweakRadio, { label: 'Base temp', value: t.temp, options: ['cool', 'neutral', 'warm'], onChange: (v) => setTweak('temp', v) }),
        React.createElement(TweakSection, { label: 'Layout' }),
        React.createElement(TweakRadio, { label: 'Density', value: t.density, options: ['compact', 'comfortable'], onChange: (v) => setTweak('density', v) }),
        React.createElement(TweakSection, { label: 'Agent sphere' }),
        React.createElement(TweakRadio, { label: 'Style', value: t.sphere, options: ['orb', 'rings', 'minimal'], onChange: (v) => setTweak('sphere', v) }),
        React.createElement(TweakSection, { label: 'Type' }),
        React.createElement(TweakSelect, { label: 'Font pairing', value: t.fontPair, options: ['grotesk', 'hanken', 'archivo'], onChange: (v) => setTweak('fontPair', v) }),
      ),
    )
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
