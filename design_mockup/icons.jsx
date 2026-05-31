/* ============================================================
   BRAIN UI — icon set (stroke glyphs, 1.6 weight, 24 grid)
   ============================================================ */
(function () {
  const P = {
    grid:    '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    sphere:  '<circle cx="12" cy="12" r="8.2"/><ellipse cx="12" cy="12" rx="8.2" ry="3.4"/><path d="M5 9.5c4 2 10 2 14 0M5 14.5c4-2 10-2 14 0"/>',
    search:  '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    inbox:   '<path d="M3.5 13.5 6 5.5a2 2 0 0 1 1.9-1.4h8.2A2 2 0 0 1 18 5.5l2.5 8"/><path d="M3.5 13.5h5l1.5 3h4l1.5-3h5v4a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2z"/>',
    merge:   '<path d="M7 4v5a5 5 0 0 0 5 5h5"/><path d="M17 4v5a5 5 0 0 1-5 5H7"/><path d="M14.5 11.5 17.5 14l-3 2.5"/>',
    cal:     '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3.5v3.5M16 3.5v3.5"/>',
    check:   '<path d="M5 12.5 9.5 17 19 6.5"/>',
    cube:    '<path d="M12 3.5 20 8v8l-8 4.5L4 16V8z"/><path d="M4 8l8 4.5L20 8M12 12.5V20.5"/>',
    flag:    '<path d="M6 21V4M6 4h11l-2.5 4L17 12H6"/>',
    book:    '<path d="M5 4.5h9a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H5z"/><path d="M5 4.5v12.5"/><path d="M17 7.5h2v12a2.5 2.5 0 0 0-2.5-2.5"/>',
    chart:   '<path d="M4 4v16h16"/><path d="M8 16v-3M12 16V9M16 16v-5"/>',
    doc:     '<path d="M6 3.5h7l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M13 3.5V9h5M8.5 13h7M8.5 16.5h7"/>',
    layers:  '<path d="M12 3.5 21 8l-9 4.5L3 8z"/><path d="M3 12l9 4.5L21 12M3 16l9 4.5L21 16"/>',
    'arrow-up':'<path d="M12 20V5M6 11l6-6 6 6"/>',
    shield:  '<path d="M12 3.5 19 6v5.5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4.5"/>',
    gear:    '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1M18.4 18.4l-2.1-2.1M7.7 7.7 5.6 5.6"/>',
    spark:   '<path d="M12 3.5 13.8 9 19.5 10.8 13.8 12.6 12 18.2 10.2 12.6 4.5 10.8 10.2 9z"/>',
    sun:     '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.5M12 19v2.5M21.5 12H19M5 12H2.5M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8M18.4 18.4l-1.8-1.8M7.4 7.4 5.6 5.6"/>',
    sync:    '<path d="M20 8a8 8 0 0 0-14-3L4 7M4 4v3h3"/><path d="M4 16a8 8 0 0 0 14 3l2-2M20 20v-3h-3"/>',
    upload:  '<path d="M12 15.5V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4.5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-3"/>',
    plus:    '<path d="M12 5v14M5 12h14"/>',
    cmd:     '<path d="M9 6.5A2.5 2.5 0 1 1 6.5 9H9zM15 6.5A2.5 2.5 0 1 0 17.5 9H15zM9 17.5A2.5 2.5 0 1 0 6.5 15H9zM15 17.5a2.5 2.5 0 1 1 2.5-2.5H15z"/><rect x="9" y="9" width="6" height="6" rx="0.5"/>',
    stop:    '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    pause:   '<rect x="7" y="5" width="3.5" height="14" rx="1"/><rect x="13.5" y="5" width="3.5" height="14" rx="1"/>',
    bolt:    '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
    globe:   '<circle cx="12" cy="12" r="8.2"/><path d="M3.8 12h16.4M12 3.8c2.4 2.2 3.8 5.1 3.8 8.2S14.4 18 12 20.2C9.6 18 8.2 15.1 8.2 12S9.6 6 12 3.8z"/>',
    file:    '<path d="M6 3.5h7l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M13 3.5V9h5"/>',
    image:   '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="8.5" cy="9.5" r="1.8"/><path d="M4 17l5-4.5 4 3.5 3-2.5 4 3.5"/>',
    x:       '<path d="M6 6l12 12M18 6 6 18"/>',
    edit:    '<path d="M5 19h3.5L18 9.5 14.5 6 5 15.5z"/><path d="M13 7.5 16.5 11"/>',
    folder:  '<path d="M3.5 6.5a2 2 0 0 1 2-2h3.2l2 2.5h7.8a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2z"/>',
    dot:     '<circle cx="12" cy="12" r="3.5"/>',
    chevron: '<path d="M9 6l6 6-6 6"/>',
    enter:   '<path d="M20 6v5a3 3 0 0 1-3 3H5"/><path d="M9 10l-4 4 4 4"/>',
  };
  function Icon({ name, size = 18, stroke = 1.6, fill = false, style }) {
    const d = P[name] || P.dot;
    return React.createElement('svg', {
      width: size, height: size, viewBox: '0 0 24 24',
      fill: fill ? 'currentColor' : 'none',
      stroke: fill ? 'none' : 'currentColor',
      strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round',
      style, dangerouslySetInnerHTML: { __html: d },
    });
  }
  window.Icon = Icon;
})();
