/* ============================================================
   BRAIN UI — AgentSphere
   A status surface, not a hero toy. Every state maps to a real
   PRD agent state. Three style variants (orb / rings / minimal).
   ============================================================ */
(function () {
  // inject keyframes once
  if (!document.getElementById('sphere-keys')) {
    const s = document.createElement('style');
    s.id = 'sphere-keys';
    s.textContent = `
    @keyframes sph-breathe { 0%,100%{transform:scale(.97);opacity:.9} 50%{transform:scale(1.03);opacity:1} }
    @keyframes sph-spin    { to { transform: rotate(360deg); } }
    @keyframes sph-spin-rev{ to { transform: rotate(-360deg); } }
    @keyframes sph-pulse   { 0%{transform:scale(.82);opacity:.7} 70%{opacity:0} 100%{transform:scale(1.35);opacity:0} }
    @keyframes sph-orbit   { to { transform: rotate(360deg); } }
    @keyframes sph-wave    { 0%,100%{transform:scaleY(.3)} 50%{transform:scaleY(1)} }
    @keyframes sph-flash   { 0%,100%{opacity:.55} 50%{opacity:1} }
    .sph-wrap{ position:relative; display:grid; place-items:center; }
    .sph-svg{ position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
    .sph-rot{ transform-origin:50% 50%; animation:sph-spin 14s linear infinite; }
    .sph-rot-fast{ transform-origin:50% 50%; animation:sph-spin 3.4s linear infinite; }
    .sph-rot-rev{ transform-origin:50% 50%; animation:sph-spin-rev 9s linear infinite; }
    .sph-orbit{ transform-origin:50% 50%; animation:sph-orbit 3.2s linear infinite; }
    .sph-orbit-slow{ transform-origin:50% 50%; animation:sph-orbit 6s linear infinite; }
    .sph-pulse{ transform-origin:50% 50%; animation:sph-pulse 2.6s ease-out infinite; }
    .sph-flash{ animation:sph-flash 1.6s ease-in-out infinite; }
    `;
    document.head.appendChild(s);
  }

  const TONE = {
    live:   'var(--live)', amber: 'var(--amber)', red: 'var(--red)',
    violet: 'var(--violet)', green: 'var(--green)', grey: 'var(--grey)',
  };

  function AgentSphere({ state = 'idle', size = 180, variant = 'orb', count }) {
    const meta = (window.AGENT_STATES || {})[state] || { tone: 'live' };
    const c = TONE[meta.tone] || TONE.live;
    const animated = !['locked', 'blocked'].includes(state);
    const breathe = ['idle', 'listening', 'speaking', 'guarded'].includes(state);

    // core orb fill differs by variant
    const coreOpacity = variant === 'rings' ? 0.10 : variant === 'minimal' ? 0.16 : 0.24;
    const coreShadow = variant === 'minimal'
      ? `0 0 ${size * 0.10}px -2px ${c}`
      : `0 0 ${size * 0.20}px -4px ${c}, inset 0 0 ${size * 0.18}px ${c}`;

    const Ring = ({ r, w = 1, dash, op = 1, cls, color }) => React.createElement('circle', {
      className: cls, cx: 50, cy: 50, r, fill: 'none',
      stroke: color || c, strokeWidth: w, strokeOpacity: op,
      strokeDasharray: dash, strokeLinecap: 'round',
    });

    const layers = [];

    // base faint ring (always, except minimal/blocked)
    if (variant !== 'minimal' && state !== 'blocked') {
      layers.push(React.createElement('g', { key: 'base' },
        Ring({ r: 46, w: 0.8, op: 0.22 }),
        variant === 'rings' && Ring({ r: 38, w: 0.6, op: 0.16 }),
      ));
    }

    // per-state overlays
    if (state === 'idle') {
      layers.push(React.createElement('g', { key: 'i', className: animated ? 'sph-rot' : '' },
        Ring({ r: 42, w: 0.8, dash: '1 7', op: 0.4 })));
    }
    if (state === 'listening') {
      layers.push(React.createElement('g', { key: 'l' },
        Ring({ r: 40, w: 1.4, op: 0.9, cls: animated ? 'sph-pulse' : '' }),
        Ring({ r: 46, w: 0.8, op: 0.5 })));
    }
    if (state === 'thinking') {
      layers.push(React.createElement('g', { key: 't' },
        React.createElement('g', { className: animated ? 'sph-rot-fast' : '' }, Ring({ r: 34, w: 2, dash: '34 80', op: 0.95 })),
        React.createElement('g', { className: animated ? 'sph-rot-rev' : '' }, Ring({ r: 42, w: 1, dash: '2 10', op: 0.5 }))));
    }
    if (state === 'speaking') {
      // ripple + waveform bars
      layers.push(React.createElement('g', { key: 's' },
        Ring({ r: 40, w: 1.2, op: 0.8, cls: animated ? 'sph-pulse' : '' })));
      const bars = [0, 1, 2, 3, 4].map((i) => React.createElement('rect', {
        key: i, x: 42 + i * 3.4, y: 44, width: 1.8, height: 12, rx: 0.9, fill: c,
        style: { transformOrigin: '50% 50%', animation: animated ? `sph-wave ${0.7 + i * 0.12}s ease-in-out infinite` : 'none', animationDelay: `${i * 0.08}s` },
      }));
      layers.push(React.createElement('g', { key: 'bars' }, bars));
    }
    if (state === 'researching' || state === 'browser') {
      layers.push(React.createElement('g', { key: 'r' },
        Ring({ r: 40, w: 0.8, dash: '2 6', op: 0.4 }),
        React.createElement('g', { className: animated ? 'sph-orbit' : '' },
          React.createElement('circle', { cx: 50, cy: 8, r: 3, fill: c })),
        state === 'browser' && Ring({ r: 30, w: 0.8, op: 0.4 }),
        state === 'browser' && React.createElement('ellipse', { cx: 50, cy: 50, rx: 30, ry: 12, fill: 'none', stroke: c, strokeWidth: 0.8, strokeOpacity: 0.4 })));
    }
    if (state === 'computeruse') {
      layers.push(React.createElement('g', { key: 'cu' },
        React.createElement('g', { className: animated ? 'sph-rot' : '' }, Ring({ r: 40, w: 2.4, dash: '20 60', op: 0.9 })),
        // cursor glyph
        React.createElement('path', { d: 'M47 44 L47 58 L51 54 L54 59 L56 58 L53 53 L58 53 Z', fill: c, opacity: 0.95 })));
    }
    if (state === 'pending') {
      layers.push(React.createElement('g', { key: 'p', className: animated ? 'sph-flash' : '' },
        Ring({ r: 42, w: 2.2, op: 1 })));
    }
    if (state === 'batch' || state === 'escalation') {
      layers.push(React.createElement('g', { key: 'seg', className: animated ? 'sph-rot' : '' },
        Ring({ r: 42, w: 2.6, dash: '10 7', op: 0.95 })));
    }
    if (state === 'blocked') {
      layers.push(React.createElement('g', { key: 'b' },
        Ring({ r: 34, w: 2.4, op: 1 }),
        React.createElement('path', { d: 'M40 40 L60 60', stroke: c, strokeWidth: 2.4, strokeLinecap: 'round' })));
    }
    if (state === 'guarded') {
      layers.push(React.createElement('g', { key: 'g' },
        Ring({ r: 42, w: 1.4, op: 0.7 }),
        React.createElement('path', {
          d: 'M50 33 L62 38 V49 c0 8-5 13-12 15 -7-2-12-7-12-15 V38 Z',
          fill: 'none', stroke: c, strokeWidth: 2, strokeLinejoin: 'round', opacity: 0.95,
        }),
        React.createElement('path', { d: 'M45 49 l4 4 7-8', fill: 'none', stroke: c, strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' })));
    }
    if (state === 'locked') {
      layers.push(React.createElement('g', { key: 'lk' },
        Ring({ r: 40, w: 1, op: 0.5, color: 'var(--grey)' })));
    }

    return React.createElement('div', {
      className: 'sph-wrap', style: { width: size, height: size },
    },
      // core orb
      React.createElement('div', {
        style: {
          width: size * 0.56, height: size * 0.56, borderRadius: '50%',
          background: `radial-gradient(circle at 38% 32%, ${c}, transparent 72%)`,
          opacity: coreOpacity,
          boxShadow: coreShadow,
          animation: breathe && animated ? 'sph-breathe 5.5s ease-in-out infinite' : 'none',
          filter: state === 'locked' ? 'grayscale(1)' : 'none',
        },
      }),
      // inner solid dot (the "presence")
      React.createElement('div', {
        style: {
          position: 'absolute', width: size * 0.13, height: size * 0.13, borderRadius: '50%',
          background: c, opacity: state === 'locked' ? 0.4 : 0.92,
          boxShadow: `0 0 ${size * 0.08}px ${c}`,
          animation: breathe && animated ? 'sph-breathe 5.5s ease-in-out infinite' : 'none',
        },
      }),
      React.createElement('svg', { className: 'sph-svg', viewBox: '0 0 100 100' }, layers),
      // count badge for batch/escalation
      (count != null && (state === 'batch' || state === 'escalation')) && React.createElement('div', {
        style: {
          position: 'absolute', right: size * 0.06, top: size * 0.06,
          minWidth: 22, height: 22, padding: '0 6px', borderRadius: 11,
          background: c, color: 'var(--bg-0)', fontWeight: 700, fontSize: 12,
          display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)',
        },
      }, count),
    );
  }

  window.AgentSphere = AgentSphere;
})();
