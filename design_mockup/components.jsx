/* ============================================================
   BRAIN UI — shared components
   ============================================================ */
(function () {
  const { Icon } = window;

  // --- tone helpers ---
  const TONE_VAR = { live: '--live', amber: '--amber', red: '--red', violet: '--violet', green: '--green', grey: '--grey' };
  const toneColor = (t) => `var(${TONE_VAR[t] || '--live'})`;
  const toneBg = (t) => ({ live: 'var(--live-bg)', amber: 'var(--amber-bg)', red: 'var(--red-bg)', violet: 'var(--violet-bg)', green: 'var(--green-bg)' }[t] || 'var(--surface-2)');
  const toneLine = (t) => ({ live: 'var(--live-line)', amber: 'var(--amber-line)', red: 'var(--red-line)', violet: 'var(--violet-line)', green: 'var(--green-line)' }[t] || 'var(--line)');

  // --- StatusDot (flat, no glow) ---
  function StatusDot({ tone = 'green', pulse }) {
    return React.createElement('span', {
      style: {
        width: 7, height: 7, borderRadius: '50%', background: toneColor(tone),
        display: 'inline-block', flex: '0 0 auto',
        animation: pulse ? 'sph-breathe 2.4s ease-in-out infinite' : 'none',
      },
    });
  }

  // --- Pill (small labelled chip) ---
  function Pill({ tone = 'grey', children, icon, solid }) {
    return React.createElement('span', {
      style: {
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '3px 9px', borderRadius: 'var(--r-pill)', fontSize: 11.5, fontWeight: 600,
        letterSpacing: '0.01em',
        color: solid ? 'var(--bg-0)' : toneColor(tone),
        background: solid ? toneColor(tone) : toneBg(tone),
        border: `1px solid ${solid ? 'transparent' : toneLine(tone)}`,
      },
    }, icon && React.createElement(Icon, { name: icon, size: 12 }), children);
  }

  // --- RiskBadge ---
  const RISK = { low: { t: 'green', l: 'Low risk' }, medium: { t: 'amber', l: 'Medium risk' }, high: { t: 'red', l: 'High risk' } };
  function RiskBadge({ level = 'low', compact }) {
    const r = RISK[level] || RISK.low;
    return React.createElement(Pill, { tone: r.t }, compact ? r.l.split(' ')[0] : r.l);
  }

  // --- ConfidenceBadge ---
  const CONF = { High: 'green', Medium: 'amber', Low: 'red' };
  function ConfidenceBadge({ level = 'High' }) {
    const dots = { High: 3, Medium: 2, Low: 1 }[level] || 1;
    return React.createElement('span', {
      style: { display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--txt-1)', fontWeight: 500 },
      title: `${level} confidence`,
    },
      React.createElement('span', { style: { display: 'inline-flex', gap: 2 } },
        [0, 1, 2].map((i) => React.createElement('span', {
          key: i, style: {
            width: 4, height: 11, borderRadius: 1,
            background: i < dots ? toneColor(CONF[level]) : 'var(--line-strong)',
          },
        }))),
      React.createElement('span', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)' } }, level),
    );
  }

  // --- ModeBadge (dropdown) ---
  function ModeBadge({ mode, modes, onSelect, onClick }) {
    const [open, setOpen] = React.useState(false);
    const ref = React.useRef(null);
    React.useEffect(() => {
      if (!open) return;
      const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
      document.addEventListener('mousedown', close);
      return () => document.removeEventListener('mousedown', close);
    }, [open]);
    const locked = mode.id === 'locked';
    const t = locked ? 'grey' : 'live';
    const hasMenu = !!(modes && onSelect);
    const toggle = () => { if (hasMenu) setOpen((o) => !o); else onClick && onClick(); };
    return React.createElement('span', { ref, style: { position: 'relative', display: 'inline-block' } },
      React.createElement('button', {
        onClick: toggle, className: 'btn btn-sm',
        style: { background: toneBg(t), borderColor: toneLine(t), color: toneColor(t), fontWeight: 600, fontSize: 12 },
      },
        React.createElement(StatusDot, { tone: t, pulse: !locked }),
        mode.label,
        React.createElement(Icon, { name: 'chevron', size: 12, style: { transform: open ? 'rotate(-90deg)' : 'rotate(90deg)', opacity: 0.6, transition: 'transform var(--fast) var(--ease)' } })),
      hasMenu && open && React.createElement('div', {
        style: {
          position: 'absolute', top: 'calc(100% + 6px)', right: 0, width: 264, zIndex: 250,
          background: 'var(--surface)', border: '1px solid var(--line-strong)', borderRadius: 'var(--r3)',
          boxShadow: 'var(--shadow-pop)', padding: 6, maxHeight: '70vh', overflowY: 'auto',
        },
      },
        React.createElement('div', { className: 'eyebrow', style: { padding: '6px 9px 4px', fontSize: 9.5 } }, 'Agent mode'),
        modes.map((m) => {
          const active = m.id === mode.id;
          const mt = m.id === 'locked' ? 'grey' : 'live';
          return React.createElement('button', {
            key: m.id, onClick: () => { onSelect(m); setOpen(false); },
            style: {
              width: '100%', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 2,
              padding: '8px 9px', borderRadius: 'var(--r2)', cursor: 'pointer',
              border: `1px solid ${active ? toneLine('live') : 'transparent'}`,
              background: active ? 'var(--live-bg)' : 'transparent',
            },
            onMouseEnter: (e) => { if (!active) e.currentTarget.style.background = 'var(--surface-2)'; },
            onMouseLeave: (e) => { if (!active) e.currentTarget.style.background = 'transparent'; },
          },
            React.createElement('span', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
              React.createElement(StatusDot, { tone: active ? mt : 'grey' }),
              React.createElement('span', { style: { fontSize: 13, fontWeight: active ? 600 : 500, color: active ? 'var(--txt-0)' : 'var(--txt-1)' } }, m.label),
              active && React.createElement('span', { style: { marginLeft: 'auto', color: 'var(--live)', display: 'flex' } }, React.createElement(Icon, { name: 'check', size: 14 }))),
            React.createElement('span', { style: { fontSize: 11, color: 'var(--txt-2)', paddingLeft: 15, lineHeight: 1.35 } }, m.desc));
        })),
    );
  }

  // --- StatusCard (metric / system tile) ---
  function StatusCard({ label, value, sub, tone, icon, dot, onClick, accent }) {
    return React.createElement('div', {
      className: 'panel', onClick,
      style: {
        padding: 'var(--s4)', display: 'flex', flexDirection: 'column', gap: 6,
        cursor: onClick ? 'pointer' : 'default',
        borderColor: accent ? toneLine(tone) : 'var(--line-soft)',
        transition: 'border-color var(--fast) var(--ease), background var(--fast)',
      },
      onMouseEnter: onClick ? (e) => { e.currentTarget.style.background = 'var(--surface-2)'; } : undefined,
      onMouseLeave: onClick ? (e) => { e.currentTarget.style.background = 'var(--surface)'; } : undefined,
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, color: 'var(--txt-2)' } },
        icon && React.createElement(Icon, { name: icon, size: 14 }),
        dot && React.createElement(StatusDot, { tone, pulse: tone === 'live' }),
        React.createElement('span', { className: 'eyebrow' }, label),
      ),
      React.createElement('div', { style: { fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', color: tone ? toneColor(tone) : 'var(--txt-0)' } }, value),
      sub && React.createElement('div', { className: 'mono', style: { fontSize: 11, color: 'var(--txt-2)' } }, sub),
    );
  }

  // --- PanelHeader ---
  function PanelHeader({ title, sub, right, icon }) {
    return React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--s3)', marginBottom: 'var(--s4)' },
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 } },
        icon && React.createElement('span', { style: { color: 'var(--txt-2)' } }, React.createElement(Icon, { name: icon, size: 16 })),
        React.createElement('div', { style: { minWidth: 0 } },
          React.createElement('div', { style: { fontSize: 14, fontWeight: 600 } }, title),
          sub && React.createElement('div', { style: { fontSize: 12, color: 'var(--txt-2)' } }, sub),
        ),
      ),
      right,
    );
  }

  // --- SourceGlyph (chatgpt / claude / etc) ---
  function SourceGlyph({ source }) {
    const map = {
      claude:   { t: 'amber',  ch: 'C' },
      chatgpt:  { t: 'green',  ch: 'G' },
      opencode: { t: 'violet', ch: 'O' },
      'claude-code': { t: 'live', ch: '⌘' },
      other:    { t: 'grey',   ch: '·' },
    };
    const m = map[source] || map.other;
    return React.createElement('span', {
      style: {
        width: 22, height: 22, borderRadius: 6, display: 'grid', placeItems: 'center',
        background: toneBg(m.t), border: `1px solid ${toneLine(m.t)}`, color: toneColor(m.t),
        fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', flex: '0 0 auto',
      },
    }, m.ch);
  }

  // --- EmptyState ---
  function EmptyState({ icon = 'inbox', title, sub }) {
    return React.createElement('div', {
      style: { display: 'grid', placeItems: 'center', gap: 10, padding: 'var(--s8) var(--s5)', textAlign: 'center', color: 'var(--txt-2)' },
    },
      React.createElement('div', {
        style: { width: 46, height: 46, borderRadius: 12, display: 'grid', placeItems: 'center', background: 'var(--surface-2)', border: '1px solid var(--line)', color: 'var(--txt-2)' },
      }, React.createElement(Icon, { name: icon, size: 20 })),
      React.createElement('div', { style: { color: 'var(--txt-1)', fontWeight: 600, fontSize: 13 } }, title),
      sub && React.createElement('div', { style: { fontSize: 12, maxWidth: 280 } }, sub),
    );
  }

  // --- TagChip (domain coloring) ---
  const DOMAIN_TONE = { project: 'live', hackathon: 'violet', course: 'green', business: 'amber', research: 'live', personal: 'grey', unknown: 'grey', ops: 'grey' };
  function TagChip({ domain }) {
    const t = DOMAIN_TONE[domain] || 'grey';
    return React.createElement('span', {
      style: { fontSize: 10.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: toneColor(t), padding: '2px 7px', borderRadius: 5, background: toneBg(t), border: `1px solid ${toneLine(t)}` },
    }, domain);
  }

  Object.assign(window, {
    StatusDot, Pill, RiskBadge, ConfidenceBadge, ModeBadge, StatusCard,
    PanelHeader, SourceGlyph, EmptyState, TagChip,
    toneColor, toneBg, toneLine, DOMAIN_TONE,
  });
})();
