/* ============================================================
   BRAIN UI — lighter screens (navigable, designed, not hi-fi)
   These show structure & intent; the 3 hi-fi screens carry depth.
   ============================================================ */
(function () {
  const { Icon, EmptyState, PanelHeader, Pill, StatusDot, RiskBadge, ConfidenceBadge, SourceGlyph, TagChip, toneColor } = window;

  function ScreenHead({ eyebrow, title, sub, right }) {
    return React.createElement('div', { style: { display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--s4)', marginBottom: 'var(--s5)' } },
      React.createElement('div', null,
        React.createElement('div', { className: 'eyebrow', style: { marginBottom: 4 } }, eyebrow),
        React.createElement('h1', { style: { margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em' } }, title),
        sub && React.createElement('div', { style: { fontSize: 13, color: 'var(--txt-2)', marginTop: 2, maxWidth: 620 } }, sub)),
      right);
  }

  // generic planned-panel stub
  function Stub({ eyebrow, title, sub, panels }) {
    return React.createElement('div', { style: { maxWidth: 1320, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow, title, sub,
        right: React.createElement(Pill, { tone: 'live' }, 'Spec — wireframe') }),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--s4)' } },
        panels.map((p, i) => React.createElement('div', { key: i, className: 'panel panel-pad', style: { minHeight: 150 } },
          React.createElement(PanelHeader, { icon: p.icon, title: p.title }),
          React.createElement('div', { style: { fontSize: 12.5, color: 'var(--txt-2)', lineHeight: 1.55 } }, p.body),
          p.items && React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 } },
            p.items.map((it, j) => React.createElement('span', { key: j, className: 'kbd', style: { fontSize: 10.5 } }, it)))))));
  }

  // ---- Research (semi-built: query + budget + scope + depth) ----
  function Research() {
    const r = window.RESEARCH;
    const budgets = [5, 10, 20, 30, 45, 60];
    const scopes = ['Web', 'Local vault', 'Gmail', 'ChatGPT/Claude', 'Drive', 'GitHub', 'Mixed'];
    const depths = ['Quick answer', 'Source roundup', 'Decision brief', 'Implementation notes'];
    return React.createElement('div', { style: { maxWidth: 1100, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow: 'Operate', title: 'Research', sub: 'Time-boxed local research. The agent returns a packet — sources, claims, confidence, and what it could not check — not an endless wander.' }),
      React.createElement('div', { className: 'panel panel-pad', style: { marginBottom: 'var(--s4)' } },
        React.createElement('div', { style: { display: 'flex', gap: 'var(--s2)', marginBottom: 'var(--s4)' } },
          React.createElement('input', { defaultValue: r.query, style: { flex: 1, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', padding: '11px 14px', color: 'var(--txt-0)', fontSize: 14, fontFamily: 'var(--font-ui)' } }),
          React.createElement('button', { className: 'btn btn-primary', style: { padding: '0 18px' } }, React.createElement(Icon, { name: 'search', size: 15 }), 'Start run')),
        React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--s5)' } },
          React.createElement('div', null, React.createElement('div', { className: 'eyebrow', style: { marginBottom: 8 } }, 'Time budget'),
            React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
              budgets.map((b) => React.createElement('button', { key: b, className: 'btn btn-sm', style: b === r.budget ? { background: 'var(--live-bg)', borderColor: 'var(--live-line)', color: 'var(--live)' } : null }, b + 'm')))),
          React.createElement('div', null, React.createElement('div', { className: 'eyebrow', style: { marginBottom: 8 } }, 'Scope'),
            React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
              scopes.map((s) => React.createElement('button', { key: s, className: 'btn btn-sm', style: (s === 'Web' || s === 'Local vault') ? { background: 'var(--live-bg)', borderColor: 'var(--live-line)', color: 'var(--live)' } : null }, s)))),
          React.createElement('div', null, React.createElement('div', { className: 'eyebrow', style: { marginBottom: 8 } }, 'Depth'),
            React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
              depths.map((d) => React.createElement('button', { key: d, className: 'btn btn-sm', style: d === r.depth ? { background: 'var(--live-bg)', borderColor: 'var(--live-line)', color: 'var(--live)' } : null }, d)))))),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s4)' } },
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement(PanelHeader, { icon: 'globe', title: 'Live progress', right: React.createElement(Pill, { tone: 'live' }, r.elapsed + ' / ' + r.budget + 'm') }),
          r.sources.map((s, i) => React.createElement('div', { key: i, style: { display: 'flex', gap: 8, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--line-soft)' } },
            React.createElement(Icon, { name: 'globe', size: 13, style: { color: 'var(--txt-3)' } }),
            React.createElement('div', { style: { flex: 1, minWidth: 0 } },
              React.createElement('div', { style: { fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, s.title),
              React.createElement('div', { className: 'mono', style: { fontSize: 10, color: 'var(--txt-3)' } }, s.url)),
            React.createElement('span', { style: { fontSize: 10, color: 'var(--txt-3)' } }, s.when)))),
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement(PanelHeader, { icon: 'doc', title: 'Findings', right: React.createElement(ConfidenceBadge, { level: r.confidence }) }),
          React.createElement('div', { style: { fontSize: 12.5, color: 'var(--txt-1)', lineHeight: 1.55, marginBottom: 12 } }, '3 claims extracted across 3 sources. Decision-brief draft ready for review before any vault write.'),
          React.createElement('div', { style: { padding: '10px 12px', borderRadius: 'var(--r2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', marginBottom: 12 } },
            React.createElement('div', { style: { fontSize: 11, color: 'var(--amber)', fontWeight: 600, marginBottom: 4 } }, 'Not checked'),
            r.gaps.map((g, i) => React.createElement('div', { key: i, style: { fontSize: 11.5, color: 'var(--txt-1)' } }, '· ' + g))),
          React.createElement('div', { style: { display: 'flex', gap: 7 } },
            React.createElement('button', { className: 'btn btn-sm', style: { flex: 1, justifyContent: 'center' } }, 'Escalate to Claude'),
            React.createElement('button', { className: 'btn btn-sm btn-primary', style: { flex: 1, justifyContent: 'center' } }, 'Save packet → vault')))));
  }

  // ---- AI Work Consolidation (semi-built) ----
  function Consolidation() {
    return React.createElement('div', { style: { maxWidth: 1100, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow: 'Intake', title: 'AI Work Consolidation', sub: 'Pull useful work out of ChatGPT / Claude / coding-agent sessions into Obsidian — decisions, snippets, next actions — without copying chat noise.' }),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '300px 1fr', gap: 'var(--s4)' } },
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement('div', { className: 'eyebrow', style: { marginBottom: 10 } }, 'Source'),
          [['claude', 'Claude'], ['chatgpt', 'ChatGPT'], ['opencode', 'OpenCode'], ['claude-code', 'Claude Code'], ['other', 'Paste / export']].map(([s, l], i) =>
            React.createElement('button', { key: i, className: 'btn', style: { width: '100%', justifyContent: 'flex-start', marginBottom: 6, background: i === 0 ? 'var(--surface-3)' : undefined } },
              React.createElement(SourceGlyph, { source: s }), l)),
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 7, marginTop: 12, fontSize: 11.5, color: 'var(--txt-2)' } },
            React.createElement(StatusDot, { tone: 'grey' }), 'Computer use · disabled — paste/export available')),
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement(PanelHeader, { icon: 'merge', title: 'Extraction preview', sub: 'Claude · "API gateway design discussion"', right: React.createElement(ConfidenceBadge, { level: 'Medium' }) }),
          React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s3)', marginBottom: 'var(--s4)' } },
            [['Decisions', '4'], ['Code snippets', '2'], ['Next actions', '3'], ['Domain', 'project']].map(([k, v], i) =>
              React.createElement('div', { key: i, style: { background: 'var(--surface-2)', borderRadius: 'var(--r2)', padding: '8px 11px' } },
                React.createElement('div', { className: 'eyebrow', style: { fontSize: 9.5 } }, k),
                React.createElement('div', { style: { fontSize: 14, fontWeight: 600, marginTop: 2 } }, v)))),
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r2)', border: '1px solid var(--line)', marginBottom: 'var(--s4)' } },
            React.createElement(Icon, { name: 'folder', size: 14, style: { color: 'var(--live)' } }),
            React.createElement('span', { className: 'mono', style: { fontSize: 11.5, flex: 1 } }, 'raw/chats/claude/2026-05-30-api-gateway.md'),
            React.createElement('button', { className: 'btn btn-sm btn-ghost', style: { padding: 5 } }, React.createElement(Icon, { name: 'edit', size: 13 }))),
          React.createElement('div', { style: { display: 'flex', gap: 7 } },
            React.createElement('button', { className: 'btn', style: { flex: 1, justifyContent: 'center' } }, 'Reject'),
            React.createElement('button', { className: 'btn', style: { flex: 1, justifyContent: 'center' } }, 'Edit'),
            React.createElement('button', { className: 'btn btn-primary', style: { flex: 1.3, justifyContent: 'center' } }, 'Apply → Obsidian')))));
  }

  // ---- Escalation Queue (semi-built table) ----
  function Escalation() {
    const st = { ready: 'live', queued: 'amber', 'in-progress': 'violet' };
    return React.createElement('div', { style: { maxWidth: 1180, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow: 'Control', title: 'Escalation Queue', sub: 'Heavy work routed to Claude Code / OpenCode with a ready handoff package. Brain UI never tries to replace the coding agents.' }),
      React.createElement('div', { className: 'panel', style: { overflow: 'hidden' } },
        React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0,2fr) 120px minmax(0,1.6fr) 120px 120px', gap: 'var(--s3)', padding: '10px var(--s4)', borderBottom: '1px solid var(--line)', background: 'var(--bg-1)' } },
          ['Task', 'Agent', 'Reason', 'Status', ''].map((h, i) => React.createElement('span', { key: i, className: 'eyebrow', style: { fontSize: 9.5 } }, h))),
        window.ESCALATIONS.map((e) => React.createElement('div', { key: e.id, style: { display: 'grid', gridTemplateColumns: 'minmax(0,2fr) 120px minmax(0,1.6fr) 120px 120px', gap: 'var(--s3)', alignItems: 'center', padding: '12px var(--s4)', borderBottom: '1px solid var(--line-soft)', fontSize: 12.5 } },
          React.createElement('div', { style: { minWidth: 0 } },
            React.createElement('div', { style: { fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, e.task),
            React.createElement('div', { className: 'mono', style: { fontSize: 10, color: 'var(--txt-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, e.repo)),
          React.createElement(Pill, { tone: e.agent === 'Claude Code' ? 'live' : 'violet' }, e.agent),
          React.createElement('span', { style: { color: 'var(--txt-2)', fontSize: 11.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, e.reason),
          React.createElement('span', { style: { display: 'flex', alignItems: 'center', gap: 6, color: toneColor(st[e.status]) } }, React.createElement(StatusDot, { tone: st[e.status] }), e.status),
          React.createElement('div', { style: { display: 'flex', gap: 6, justifyContent: 'flex-end' } },
            React.createElement('button', { className: 'btn btn-sm btn-ghost', style: { padding: 6 }, title: 'Copy handoff prompt' }, React.createElement(Icon, { name: 'doc', size: 14 })),
            React.createElement('button', { className: 'btn btn-sm btn-ghost', style: { padding: 6 }, title: 'Open repo' }, React.createElement(Icon, { name: 'folder', size: 14 })))))));
  }

  // ---- Tool Safety / NemoClaw (semi-built) ----
  function ToolSafety() {
    const rows = [window.SYSTEM.nemoclaw, window.SYSTEM.openclaw, window.SYSTEM.browser, window.SYSTEM.computer, window.SYSTEM.mcp];
    const stTone = { ready: 'green', idle: 'live', partial: 'amber', disabled: 'grey', blocked: 'red' };
    return React.createElement('div', { style: { maxWidth: 1180, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow: 'Control', title: 'Tool Safety · NemoClaw / OpenShell', sub: 'The trust surface — runtime guardrail status, permission levels, recent tool calls, denied actions, and the emergency lock.',
        right: React.createElement('button', { className: 'btn', style: { background: 'var(--red-bg)', borderColor: 'var(--red-line)', color: 'var(--red)', fontWeight: 600 } }, React.createElement(Icon, { name: 'stop', size: 15 }), 'Emergency lock') }),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s4)' } },
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement(PanelHeader, { icon: 'shield', title: 'Runtime guardrail' }),
          rows.map((s, i) => React.createElement('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0', borderBottom: '1px solid var(--line-soft)' } },
            React.createElement(StatusDot, { tone: stTone[s.state], pulse: s.state === 'ready' }),
            React.createElement('div', { style: { flex: 1 } },
              React.createElement('div', { style: { fontSize: 12.5, fontWeight: 500 } }, s.label),
              React.createElement('div', { className: 'mono', style: { fontSize: 10.5, color: 'var(--txt-2)' } }, s.detail)),
            React.createElement('span', { style: { fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', color: toneColor(stTone[s.state]) } }, s.state)))),
        React.createElement('div', { className: 'panel panel-pad' },
          React.createElement(PanelHeader, { icon: 'cmd', title: 'Recent tool calls' }),
          [['vault.read', 'low', true], ['web.search', 'low', true], ['vault.write', 'medium', true], ['email.send', 'high', false]].map(([t, r, ok], i) =>
            React.createElement('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--line-soft)' } },
              React.createElement(StatusDot, { tone: ok ? 'green' : 'red' }),
              React.createElement('span', { className: 'mono', style: { fontSize: 11.5, flex: 1 } }, t),
              React.createElement(RiskBadge, { level: r, compact: true }),
              React.createElement('span', { style: { fontSize: 10.5, color: ok ? 'var(--txt-2)' : 'var(--red)', minWidth: 56, textAlign: 'right' } }, ok ? 'allowed' : 'denied'))),
          React.createElement('div', { style: { fontSize: 10.5, color: 'var(--txt-3)', marginTop: 10 } }, 'Full log → ops/tool-logs/2026-05-30-tool-log.md'))));
  }

  // ---- Calendar (semi-built candidate table) ----
  function Calendar() {
    const cands = [
      { d: '2026-06-02', t: '14:00', dur: '90m', title: 'MAT292 PS7 work block', appr: true },
      { d: '2026-06-03', t: '10:00', dur: '60m', title: 'Hack the North retro', appr: false },
      { d: '2026-06-04', t: '16:00', dur: '45m', title: 'Tutoring SaaS customer call', appr: false },
    ];
    return React.createElement('div', { style: { maxWidth: 1080, margin: '0 auto' } },
      React.createElement(ScreenHead, { eyebrow: 'Intake', title: 'Calendar Candidates', sub: 'Proposed events stay here until you approve them. Google Calendar remains the source of truth — nothing is written without an explicit export.',
        right: React.createElement('div', { style: { display: 'flex', gap: 8 } },
          React.createElement('button', { className: 'btn' }, React.createElement(Icon, { name: 'cal', size: 15 }), 'Export .ics'),
          React.createElement('button', { className: 'btn btn-primary' }, 'Open in calendar')) }),
      React.createElement('div', { className: 'panel', style: { overflow: 'hidden' } },
        React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '120px 70px 70px minmax(0,1fr) 110px 80px', gap: 'var(--s3)', padding: '10px var(--s4)', borderBottom: '1px solid var(--line)', background: 'var(--bg-1)' } },
          ['Date', 'Time', 'Dur', 'Title', 'Approved', ''].map((h, i) => React.createElement('span', { key: i, className: 'eyebrow', style: { fontSize: 9.5 } }, h))),
        cands.map((c, i) => React.createElement('div', { key: i, style: { display: 'grid', gridTemplateColumns: '120px 70px 70px minmax(0,1fr) 110px 80px', gap: 'var(--s3)', alignItems: 'center', padding: '11px var(--s4)', borderBottom: '1px solid var(--line-soft)', fontSize: 12.5 } },
          React.createElement('span', { className: 'mono', style: { fontSize: 11.5 } }, c.d),
          React.createElement('span', { className: 'mono', style: { fontSize: 11.5 } }, c.t),
          React.createElement('span', { className: 'mono', style: { fontSize: 11.5, color: 'var(--txt-2)' } }, c.dur),
          React.createElement('span', { style: { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, c.title),
          c.appr ? React.createElement(Pill, { tone: 'green' }, 'Yes') : React.createElement(Pill, { tone: 'amber' }, 'No'),
          React.createElement('button', { className: 'btn btn-sm btn-ghost', style: { padding: 5, justifySelf: 'end' } }, React.createElement(Icon, { name: 'edit', size: 13 }))))));
  }

  // map of stub screens
  window.SCREENS_EXTRA = {
    research: Research,
    consolidate: Consolidation,
    escalation: Escalation,
    safety: ToolSafety,
    calendar: Calendar,
    tasks: () => React.createElement(Stub, { eyebrow: 'Intake', title: 'Tasks', sub: 'A live table over ops/task-db.md — no manual Markdown editing.', panels: [
      { icon: 'check', title: 'Task table', body: 'Status / area / priority filters, inline edit, next-action field. Rows can be proposed from email, research, and chat consolidation.', items: ['filter: status', 'filter: area', 'add task', 'archive done'] },
      { icon: 'merge', title: 'Proposed rows', body: '5 task rows extracted from today\'s standup note are waiting to be added.', items: ['standup → 5 tasks'] }] }),
    projects: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Projects', sub: 'Manage projects and hand off heavy work to Claude Code / OpenCode.', panels: [
      { icon: 'cube', title: 'Brain UI', body: 'Active · repo brain-ui · 4 raw files · 3 escalations · wiki synced.', items: ['Open repo', 'Claude Code', 'Closeout', 'Add resume row'] },
      { icon: 'cube', title: 'Robotics arm 2024', body: 'Archived · backfill queued · closeout escalated to OpenCode.', items: ['Generate handoff'] },
      { icon: 'cube', title: 'Portfolio site', body: 'In progress · demo link set · 2 sessions linked.', items: ['Open demo', 'Consolidate chats'] }] }),
    hackathons: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Hackathons', sub: 'Archived separately from normal projects.', panels: [
      { icon: 'flag', title: 'Hack the North 2025', body: 'Team of 4 · AI theme · finalist. Devpost + repo linked. Resume row pending.', items: ['Devpost', 'Repo', 'Archive'] },
      { icon: 'flag', title: 'UofT Hacks 2025', body: 'Solo · health theme. Wiki archived, resume row added.', items: ['Wiki page'] }] }),
    courses: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Courses', sub: 'Semester setup, source organization, weak-concept tracking, Quercus/Canvas intake. AI helps you learn — it does not silently solve graded work.', panels: [
      { icon: 'book', title: 'MAT292 · Calculus III', body: 'Laplace transforms flagged as a weak concept. PS6 due. Lecture 18 staged in inbox.', items: ['Upload lecture', 'Weak concepts', 'Study plan'] },
      { icon: 'book', title: 'ECE253 · Digital Systems', body: 'Syllabus + 4 lectures ingested. AI policy: hints only.', items: ['Past exams'] },
      { icon: 'book', title: 'ESC203 · Eng & Society', body: 'Team charter staged. Assignment intake active.', items: ['Assignments'] }] }),
    business: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Business', sub: 'A first-class category — never forced into project / course buckets. Legal & finance routing requires review.', panels: [
      { icon: 'chart', title: 'Tutoring SaaS', body: 'Customer-discovery notes + AWS invoice staged. Pipeline: validation.', items: ['Market research', 'Finance', 'Sales'] },
      { icon: 'chart', title: 'New area', body: 'OpenClaw can propose a new business area from classified docs — you approve it.', items: ['Propose area'] }] }),
    resume: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Resume Pipeline', sub: 'Which projects / hackathons / business work can become resume evidence.', panels: [
      { icon: 'doc', title: 'Evidence rows', body: '6 rows tracked over ops/resume-pipeline.md — bullet status, interview-story status, GitHub/demo links.', items: ['Add row', 'Filter status'] },
      { icon: 'spark', title: 'Pull evidence', body: 'Draw from project closeouts, hackathon archives, chats, and browser research.', items: ['From closeout'] }] }),
    backfill: () => React.createElement(Stub, { eyebrow: 'Work', title: 'Backfill', sub: 'Process prior work into the vault — repo inventory with closeout workflows.', panels: [
      { icon: 'layers', title: 'Repo inventory', body: '32 repos · 11 archived · 34% complete. Filter by type / value / status.', items: ['Not started', 'Queued', 'In progress', 'Escalated'] },
      { icon: 'arrow-up', title: 'High-priority queue', body: 'Generate Claude Code / OpenCode handoff for repo backfill.', items: ['Generate handoff'] }] }),
    settings: () => React.createElement(Stub, { eyebrow: 'Control', title: 'Settings', sub: 'Configuration without overwhelm. Paths, runtime config, model provider, and approval preferences.', panels: [
      { icon: 'folder', title: 'Paths', body: 'Vault path · old repo path · new repo path · brain.cmd path.', items: ['OBSIDIAN_VAULT_PATH', 'BRAIN_CMD_PATH', 'OLD_BRAIN_REPO_PATH'] },
      { icon: 'sphere', title: 'OpenClaw', body: 'Base URL · local model provider (Ollama) · default model.', items: ['LOCAL_MODEL_PROVIDER', 'OLLAMA_BASE_URL'] },
      { icon: 'shield', title: 'NemoClaw / OpenShell', body: 'Runtime URL · policy path · default mode · network policy · allowed dirs.', items: ['NEMOCLAW_ENABLED', 'NEMOCLAW_DEFAULT_MODE', 'NETWORK_POLICY'] },
      { icon: 'cmd', title: 'Harness toggles', body: 'Browser harness · computer use · MCP gateway — off by default.', items: ['ENABLE_BROWSER_HARNESS', 'ENABLE_COMPUTER_USE'] },
      { icon: 'check', title: 'Approval prefs', body: 'Tune which medium-risk actions batch vs. auto-run.', items: ['Batch threshold'] },
      { icon: 'arrow-up', title: 'Heavy agents', body: 'Claude Code / OpenCode executable paths for escalation launch.', items: ['CLAUDE_CODE_PATH', 'OPENCODE_PATH'] }] }),
  };
})();
