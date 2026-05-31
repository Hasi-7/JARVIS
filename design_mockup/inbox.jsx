/* ============================================================
   BRAIN UI — Raw Inbox (frictionless intake + classification)
   ============================================================ */
(function () {
  const { Icon, StatusDot, Pill, PanelHeader, ConfidenceBadge, RiskBadge, TagChip, SourceGlyph, EmptyState, toneColor, DOMAIN_TONE } = window;
  const { useState, useRef } = React;

  const KIND_ICON = { pdf: 'file', img: 'image', md: 'doc', txt: 'doc', doc: 'doc', other: 'file' };

  // tiny deterministic classifier for newly-dropped files
  function classify(name) {
    const n = name.toLowerCase();
    if (/lecture|l\d|syllabus|exam|assignment|mat\d|ece\d|esc\d|phy\d|aer\d/.test(n))
      return { domain: 'course', entity: 'MAT292', source: 'lecture', dest: 'raw/courses/MAT292/lectures/', conf: 'Medium', reason: 'Filename pattern suggests course material' };
    if (/screenshot|\.png|\.jpg|ui|mock/.test(n))
      return { domain: 'project', entity: 'Brain UI', source: 'screenshots', dest: 'raw/projects/Brain UI/screenshots/', conf: 'Medium', reason: 'Image in active project context' };
    if (/devpost|hack|submission/.test(n))
      return { domain: 'hackathon', entity: 'Hack the North 2025', source: 'submission', dest: 'raw/hackathons/Hack the North 2025/', conf: 'Medium', reason: 'Hackathon submission artifact' };
    if (/invoice|finance|receipt|pitch|customer/.test(n))
      return { domain: 'business', entity: 'Tutoring SaaS', source: 'finance', dest: 'raw/business/Tutoring SaaS/finance/', conf: 'Low', reason: 'Finance/business — flagged for review' };
    return { domain: 'unknown', entity: '—', source: 'other', dest: 'raw/inbox/unclassified/', conf: 'Low', reason: 'No strong signal — defaulted to inbox' };
  }

  function FileRow({ f, selected, onSelect, onToggleCheck, checked }) {
    const classifying = f.status === 'classifying';
    return React.createElement('div', {
      onClick: () => onSelect(f.id),
      style: {
        display: 'grid', gridTemplateColumns: '24px minmax(0,2.2fr) 96px 1fr 84px 96px',
        alignItems: 'center', gap: 'var(--s3)', padding: '0 var(--s4)', height: 'var(--row-h)',
        borderBottom: '1px solid var(--line-soft)', cursor: 'pointer', fontSize: 12.5,
        background: selected ? 'var(--surface-2)' : 'transparent',
        borderLeft: `2px solid ${selected ? 'var(--live)' : 'transparent'}`,
        transition: 'background var(--fast)',
      },
      onMouseEnter: (e) => { if (!selected) e.currentTarget.style.background = 'var(--surface-2)'; },
      onMouseLeave: (e) => { if (!selected) e.currentTarget.style.background = 'transparent'; },
    },
      React.createElement('input', { type: 'checkbox', checked: !!checked, onClick: (e) => e.stopPropagation(), onChange: () => onToggleCheck(f.id), style: { accentColor: 'var(--live)', width: 14, height: 14 } }),
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 } },
        React.createElement('span', { style: { color: 'var(--txt-2)', flex: '0 0 auto' } }, React.createElement(Icon, { name: KIND_ICON[f.kind] || 'file', size: 15 })),
        React.createElement('div', { style: { minWidth: 0 } },
          React.createElement('div', { className: 'mono', style: { fontSize: 11.5, color: 'var(--txt-0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, f.name),
          React.createElement('div', { style: { fontSize: 10, color: 'var(--txt-3)' } }, f.size))),
      classifying
        ? React.createElement('span', { style: { display: 'flex', alignItems: 'center', gap: 6, color: 'var(--live)', fontSize: 11 } }, React.createElement('span', { className: 'sph-flash' }, '◍'), 'classifying')
        : React.createElement(TagChip, { domain: f.domain }),
      classifying
        ? React.createElement('div', { style: { height: 4, background: 'var(--surface-3)', borderRadius: 2, overflow: 'hidden' } }, React.createElement('div', { style: { width: '40%', height: '100%', background: 'var(--live)', borderRadius: 2, animation: 'sph-breathe 1.2s ease-in-out infinite' } }))
        : React.createElement('span', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, f.dest),
      classifying ? React.createElement('span', null) : React.createElement(ConfidenceBadge, { level: f.conf }),
      classifying ? React.createElement('span', null) : React.createElement('span', null,
        f.status === 'review'
          ? React.createElement(Pill, { tone: 'amber' }, 'Review')
          : React.createElement(Pill, { tone: 'live' }, 'Pending')),
    );
  }

  function Detail({ f, onClose, onApprove, onReject }) {
    if (!f) return React.createElement('div', { className: 'panel', style: { padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' } },
      React.createElement(EmptyState, { icon: 'inbox', title: 'No file selected', sub: 'Pick a row to review its classification, edit the destination, or override the domain.' }));
    const tone = DOMAIN_TONE[f.domain] || 'grey';
    return React.createElement('div', { className: 'panel', style: { display: 'flex', flexDirection: 'column', minHeight: 0 } },
      React.createElement('div', { style: { padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 } },
        React.createElement('span', { style: { color: 'var(--txt-2)' } }, React.createElement(Icon, { name: KIND_ICON[f.kind] || 'file', size: 18 })),
        React.createElement('div', { style: { flex: 1, minWidth: 0 } },
          React.createElement('div', { className: 'mono', style: { fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, f.name),
          React.createElement('div', { style: { fontSize: 10.5, color: 'var(--txt-3)' } }, f.size + ' · staged')),
        React.createElement('button', { className: 'btn btn-sm btn-ghost', onClick: onClose, style: { padding: 6 } }, React.createElement(Icon, { name: 'x', size: 15 }))),
      React.createElement('div', { style: { padding: 'var(--s5)', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--s4)' } },
        // classification proposal
        React.createElement('div', null,
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 8 } }, 'AI classification'),
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 } },
            React.createElement(TagChip, { domain: f.domain }), React.createElement(ConfidenceBadge, { level: f.conf }),
            React.createElement('span', { style: { marginLeft: 'auto' } }, React.createElement(RiskBadge, { level: f.status === 'review' ? 'medium' : 'low', compact: true }))),
          React.createElement('div', { style: { fontSize: 12, color: 'var(--txt-1)', lineHeight: 1.5, padding: '10px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r2)', border: '1px solid var(--line-soft)' } },
            React.createElement('span', { style: { color: 'var(--txt-3)' } }, 'Reason · '), f.reason)),
        // editable fields
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s3)' } },
          [['Domain', f.domain], ['Entity', f.entity], ['Source type', f.source]].map(([k, v], i) =>
            React.createElement('div', { key: i, style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 } },
              React.createElement('span', { className: 'eyebrow' }, k),
              React.createElement('div', { className: 'btn btn-sm', style: { fontFamily: 'var(--font-mono)', fontSize: 11.5 } }, v, React.createElement(Icon, { name: 'chevron', size: 12, style: { transform: 'rotate(90deg)', opacity: 0.5 } }))))),
        // destination
        React.createElement('div', null,
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 8 } }, 'Proposed destination'),
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r2)', border: `1px solid ${toneColor(tone)}`, borderColor: 'var(--line)' } },
            React.createElement(Icon, { name: 'folder', size: 14, style: { color: toneColor(tone), flex: '0 0 auto' } }),
            React.createElement('span', { className: 'mono', style: { fontSize: 11.5, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, f.dest),
            React.createElement('button', { className: 'btn btn-sm btn-ghost', style: { padding: 5 } }, React.createElement(Icon, { name: 'edit', size: 13 }))),
          React.createElement('div', { style: { fontSize: 10.5, color: 'var(--txt-3)', marginTop: 6 } }, 'Original upload is never deleted · existing files never overwritten without confirmation.')),
      ),
      React.createElement('div', { style: { padding: 'var(--s4) var(--s5)', borderTop: '1px solid var(--line)', display: 'flex', gap: 'var(--s2)' } },
        React.createElement('button', { className: 'btn', style: { flex: 1, justifyContent: 'center' }, onClick: () => onReject(f.id) }, 'Reject'),
        React.createElement('button', { className: 'btn', style: { flex: 1, justifyContent: 'center' } }, React.createElement(Icon, { name: 'edit', size: 13 }), 'Override'),
        React.createElement('button', { className: 'btn btn-primary', style: { flex: 1.4, justifyContent: 'center' }, onClick: () => onApprove(f.id) }, React.createElement(Icon, { name: 'check', size: 14 }), 'Route file')),
    );
  }

  function RawInbox() {
    const [files, setFiles] = useState(window.RAW_FILES);
    const [sel, setSel] = useState(window.RAW_FILES[0].id);
    const [checked, setChecked] = useState({});
    const [drag, setDrag] = useState(false);
    const inputRef = useRef(null);

    const addFiles = (list) => {
      const incoming = Array.from(list).map((file, i) => ({
        id: 'n' + Date.now() + i, name: file.name || ('dropped-' + (i + 1) + '.pdf'),
        size: file.size ? (file.size / 1024 > 1024 ? (file.size / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(file.size / 1024)) + ' KB') : '— KB',
        kind: /\.(png|jpg|jpeg|heic|gif)$/i.test(file.name || '') ? 'img' : /\.(md)$/i.test(file.name || '') ? 'md' : /\.(txt)$/i.test(file.name || '') ? 'txt' : /\.(docx?)$/i.test(file.name || '') ? 'doc' : 'pdf',
        status: 'classifying', domain: 'unknown', entity: '—', source: 'other', dest: '…', conf: 'Low', reason: '',
      }));
      setFiles((prev) => [...incoming, ...prev]);
      incoming.forEach((nf, idx) => setTimeout(() => {
        const c = classify(nf.name);
        setFiles((prev) => prev.map((x) => x.id === nf.id ? { ...x, ...c, status: c.conf === 'Low' ? 'review' : 'pending' } : x));
      }, 900 + idx * 500));
    };

    const onDrop = (e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files); else addFiles([{ name: 'pasted-note-' + Date.now() + '.md' }]); };
    const approve = (id) => { setFiles((p) => p.filter((x) => x.id !== id)); setSel(null); };
    const reject = (id) => { setFiles((p) => p.filter((x) => x.id !== id)); setSel(null); };
    const checkedCount = Object.values(checked).filter(Boolean).length;
    const highConf = files.filter((f) => f.conf === 'High' && f.status === 'pending').length;
    const current = files.find((f) => f.id === sel);

    return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 'var(--s5)', height: '100%', maxWidth: 1440, margin: '0 auto' } },
      // header
      React.createElement('div', { style: { display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--s4)' } },
        React.createElement('div', null,
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 4 } }, 'Intake'),
          React.createElement('h1', { style: { margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em' } }, 'Raw Inbox'),
          React.createElement('div', { style: { fontSize: 13, color: 'var(--txt-2)', marginTop: 2 } }, 'Drop files. The agent classifies and proposes a destination — you never type folder paths.')),
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
          React.createElement('span', { style: { display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--txt-2)' } }, React.createElement(StatusDot, { tone: 'green' }), 'brain sync-raw · synced 12:41'),
          React.createElement('button', { className: 'btn', onClick: () => inputRef.current?.click() }, React.createElement(Icon, { name: 'upload', size: 15 }), 'Select files'))),

      // dropzone
      React.createElement('div', {
        onDragOver: (e) => { e.preventDefault(); setDrag(true); }, onDragLeave: () => setDrag(false), onDrop,
        onClick: () => inputRef.current?.click(),
        style: {
          border: `1.5px dashed ${drag ? 'var(--live)' : 'var(--line-strong)'}`, borderRadius: 'var(--r3)',
          background: drag ? 'var(--live-bg)' : 'var(--bg-1)', padding: 'var(--s5)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--s3)', color: drag ? 'var(--live)' : 'var(--txt-2)',
          transition: 'all var(--fast) var(--ease)', flex: '0 0 auto',
        },
      },
        React.createElement(Icon, { name: 'upload', size: 18 }),
        React.createElement('span', { style: { fontSize: 13, fontWeight: 500 } }, drag ? 'Release to stage & classify' : 'Drag files here, or click to select'),
        React.createElement('input', { ref: inputRef, type: 'file', multiple: true, style: { display: 'none' }, onChange: (e) => { if (e.target.files?.length) addFiles(e.target.files); e.target.value = ''; } })),

      // body: table + detail
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 372px', gap: 'var(--s5)', flex: 1, minHeight: 0 } },
        // table
        React.createElement('div', { className: 'panel', style: { display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' } },
          // batch bar
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 'var(--s3)', padding: '10px var(--s4)', borderBottom: '1px solid var(--line)' } },
            React.createElement('span', { style: { fontSize: 12.5, fontWeight: 600 } }, files.length + ' staged'),
            checkedCount > 0 && React.createElement(Pill, { tone: 'live' }, checkedCount + ' selected'),
            React.createElement('div', { style: { flex: 1 } }),
            React.createElement('button', { className: 'btn btn-sm', disabled: !highConf, style: { opacity: highConf ? 1 : 0.5 } }, React.createElement(Icon, { name: 'check', size: 13 }), `Batch approve ${highConf} high-conf`),
            React.createElement('button', { className: 'btn btn-sm btn-primary' }, React.createElement(Icon, { name: 'sync', size: 13 }), 'Sync raw')),
          // column header
          React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '24px minmax(0,2.2fr) 96px 1fr 84px 96px', gap: 'var(--s3)', padding: '8px var(--s4)', borderBottom: '1px solid var(--line)', background: 'var(--bg-1)' } },
            ['', 'File', 'Domain', 'Destination', 'Conf.', 'Status'].map((h, i) =>
              React.createElement('span', { key: i, className: 'eyebrow', style: { fontSize: 9.5 } }, h))),
          // rows
          React.createElement('div', { style: { flex: 1, overflowY: 'auto' } },
            files.length === 0
              ? React.createElement(EmptyState, { icon: 'check', title: 'Inbox clear', sub: 'All staged files have been routed.' })
              : files.map((f) => React.createElement(FileRow, { key: f.id, f, selected: sel === f.id, onSelect: setSel, checked: checked[f.id], onToggleCheck: (id) => setChecked((c) => ({ ...c, [id]: !c[id] })) }))),
        ),
        // detail
        React.createElement(Detail, { f: current, onClose: () => setSel(null), onApprove: approve, onReject: reject }),
      ),
    );
  }

  window.RawInbox = RawInbox;
})();
