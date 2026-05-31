/* ============================================================
   BRAIN UI — mock data
   Represents Hasnain's world so screens feel lived-in.
   ============================================================ */

// --- agent state model (maps 1:1 to PRD sphere states) ---
window.AGENT_STATES = {
  idle:        { label: 'Idle',              tone: 'live',   blurb: 'Resident · breathing' },
  listening:   { label: 'Listening',         tone: 'live',   blurb: 'Capturing input' },
  thinking:    { label: 'Thinking',          tone: 'live',   blurb: 'Local model reasoning' },
  speaking:    { label: 'Speaking',          tone: 'live',   blurb: 'Responding' },
  researching: { label: 'Researching',       tone: 'live',   blurb: 'Browser harness · time-boxed' },
  browser:     { label: 'Browser active',    tone: 'live',   blurb: 'Operating a page' },
  computeruse: { label: 'Computer use',      tone: 'live',   blurb: 'Driving approved UI' },
  pending:     { label: 'Tool request',      tone: 'amber',  blurb: '1 action awaiting approval' },
  batch:       { label: 'Batch approval',    tone: 'amber',  blurb: '6 changes queued' },
  escalation:  { label: 'Escalation ready',  tone: 'violet', blurb: 'Handoff prepared' },
  blocked:     { label: 'Blocked',           tone: 'red',    blurb: 'Action denied by policy' },
  guarded:     { label: 'Guarded',           tone: 'green',  blurb: 'NemoClaw / OpenShell active' },
  locked:      { label: 'Locked',            tone: 'grey',   blurb: 'Tools disabled · manual' },
};

// --- progressive autonomy modes ---
window.AGENT_MODES = [
  { id: 'manual',   label: 'Manual',       desc: 'You drive. Agent can be off.' },
  { id: 'observe',  label: 'Observe',      desc: 'Reads app state, answers questions. No tools run.' },
  { id: 'draft',    label: 'Draft',        desc: 'Generates proposals. Nothing is applied.' },
  { id: 'assist',   label: 'Assist',       desc: 'Runs low-risk tools. Batches medium-risk for approval.' },
  { id: 'research', label: 'Research',     desc: 'Time-boxed browser harness. Produces a research packet.' },
  { id: 'computer', label: 'Computer Use', desc: 'Operates approved UI flows. Visibly supervised.' },
  { id: 'locked',   label: 'Locked',       desc: 'All agent tools disabled. UI works manually.' },
];

// --- system / runtime status ---
window.SYSTEM = {
  vault: 'D:\\Hasnain\\Obsidian\\AI-Command-Center',
  brainCmd: 'D:\\Hasnain\\Personal\\bin\\brain.cmd',
  openclaw:  { state: 'ready',     label: 'OpenClaw',          detail: 'qwen2.5:14b · Ollama' },
  nemoclaw:  { state: 'ready',     label: 'NemoClaw/OpenShell',detail: 'policy v3 · restricted net' },
  browser:   { state: 'idle',      label: 'Browser harness',   detail: 'Playwright · ready' },
  computer:  { state: 'disabled',  label: 'Computer use',      detail: 'Disabled in settings' },
  model:     { state: 'ready',     label: 'Local model',       detail: 'qwen2.5:14b' },
  mcp:       { state: 'partial',   label: 'MCP gateway',       detail: '3 of 5 connected' },
};

// --- quick actions (dashboard + palette) ---
window.QUICK_ACTIONS = [
  { id: 'ask',        label: 'Ask Agent',         glyph: 'spark',  group: 'Agent' },
  { id: 'research',   label: 'Research Topic',    glyph: 'search', group: 'Agent' },
  { id: 'consolidate',label: 'Consolidate AI Work',glyph: 'merge', group: 'Agent' },
  { id: 'today',      label: 'Run brain today',   glyph: 'sun',    group: 'Brain CLI', cmd: 'brain today' },
  { id: 'weekly',     label: 'Run brain weekly',  glyph: 'cal',    group: 'Brain CLI', cmd: 'brain weekly' },
  { id: 'syncraw',    label: 'Sync Raw',          glyph: 'sync',   group: 'Brain CLI', cmd: 'brain sync-raw' },
  { id: 'calexport',  label: 'Export Calendar',   glyph: 'cal',    group: 'Brain CLI', cmd: 'brain calendar-export' },
  { id: 'upload',     label: 'Upload Raw File',   glyph: 'upload', group: 'Intake' },
  { id: 'newproj',    label: 'New Project',       glyph: 'plus',   group: 'Create', cmd: 'brain new-project' },
  { id: 'newhack',    label: 'New Hackathon',     glyph: 'plus',   group: 'Create', cmd: 'brain new-hackathon' },
  { id: 'newcourse',  label: 'New Course',        glyph: 'plus',   group: 'Create', cmd: 'brain new-course' },
];

// --- today's plan ---
window.TODAY = {
  date: 'Fri · May 30',
  focus: 'MAT292 problem set 6 + Brain UI handoff',
  blocks: [
    { time: '09:30', dur: '90m', title: 'MAT292 — Laplace transforms PS6', tag: 'course', done: true },
    { time: '11:30', dur: '45m', title: 'Stand-up notes → vault', tag: 'ops', done: true },
    { time: '13:00', dur: '120m', title: 'Brain UI — agent cockpit build', tag: 'project', done: false, now: true },
    { time: '15:30', dur: '60m', title: 'Review research packet: NemoClaw policy', tag: 'research', done: false },
    { time: '17:00', dur: '45m', title: 'Hack the North — submission draft', tag: 'hackathon', done: false },
  ],
};

// --- pending approvals (batch) ---
window.APPROVALS = [
  { id: 'ap1', type: 'file_route',     risk: 'medium', conf: 'High',   title: 'Route 4 lecture PDFs → courses/MAT292/lectures', files: 4, reason: 'Filenames + headers match MAT292 lecture series' },
  { id: 'ap2', type: 'chat_consolidation', risk: 'medium', conf: 'Medium', title: 'Save Claude session "API gateway design" → projects/Brain UI', files: 1, reason: 'Conversation references repo brain-ui and FastAPI gateway' },
  { id: 'ap3', type: 'calendar_candidate', risk: 'medium', conf: 'High', title: 'Add 3 calendar candidates from PS deadlines', files: 3, reason: 'Extracted from Quercus email digest' },
  { id: 'ap4', type: 'task_add',       risk: 'low',    conf: 'High',   title: 'Add 5 task rows from today\'s standup note', files: 5, reason: 'Action items detected in standup.md' },
];

// --- escalations to heavy agents ---
window.ESCALATIONS = [
  { id: 'es1', task: 'Refactor brain CLI command broker for async', agent: 'Claude Code', reason: 'Multi-file change across 14 modules — exceeds local model reliability', repo: 'D:\\...\\brain-ui\\backend', status: 'ready' },
  { id: 'es2', task: 'Backfill closeout: robotics-arm-2024 repo', agent: 'OpenCode',    reason: 'Large repo synthesis + archive generation', repo: 'D:\\...\\robotics-arm-2024', status: 'queued' },
  { id: 'es3', task: 'Implement Research packet → Obsidian writer', agent: 'Claude Code', reason: 'Implementation-ready plan needed from research notes', repo: 'D:\\...\\brain-ui', status: 'in-progress' },
];

// --- recent consolidated AI work ---
window.CONSOLIDATED = [
  { id: 'c1', source: 'claude',  title: 'API gateway design discussion', dest: 'raw/chats/claude/', when: '2h ago', items: '4 decisions · 2 snippets' },
  { id: 'c2', source: 'chatgpt', title: 'Laplace transform intuition',   dest: 'raw/courses/MAT292/', when: 'Yesterday', items: '6 notes · 1 next action' },
  { id: 'c3', source: 'opencode',title: 'Session: vault lint pass',       dest: 'raw/chats/opencode/', when: 'Yesterday', items: '3 fixes · 1 task' },
];

// --- recent command output ---
window.CMD_LOG = [
  { cmd: 'brain status', ok: true, at: '13:02', out: 'vault OK · 1,284 notes · 7 raw pending · last backup 04:00' },
  { cmd: 'brain sync-raw', ok: true, at: '12:41', out: 'synced 7 files · 0 conflicts' },
  { cmd: 'brain doctor', ok: true, at: '09:15', out: 'all checks passed (12/12)' },
];

// --- raw inbox staging files (classification proposals) ---
window.RAW_FILES = [
  { id: 'r1', name: 'MAT292-L18-laplace.pdf',  size: '2.4 MB', kind: 'pdf',  domain: 'course',   entity: 'MAT292', source: 'lecture',          dest: 'raw/courses/MAT292/lectures/', conf: 'High',   reason: 'Header "MAT292 Lecture 18" + course calendar match', status: 'pending' },
  { id: 'r2', name: 'screenshot-2026-05-30.png',size: '880 KB', kind: 'img', domain: 'project',  entity: 'Brain UI', source: 'screenshots',     dest: 'raw/projects/Brain UI/screenshots/', conf: 'Medium', reason: 'UI screenshot, matches active project context', status: 'pending' },
  { id: 'r3', name: 'devpost-submission.md',    size: '14 KB',  kind: 'md',  domain: 'hackathon',entity: 'Hack the North 2025', source: 'submission', dest: 'raw/hackathons/Hack the North 2025/', conf: 'High', reason: 'Devpost export markdown', status: 'pending' },
  { id: 'r4', name: 'customer-call-notes.txt',  size: '6 KB',   kind: 'txt', domain: 'business', entity: 'Tutoring SaaS', source: 'customer-discovery', dest: 'raw/business/Tutoring SaaS/customer-discovery/', conf: 'Medium', reason: 'Mentions interviews + pricing feedback', status: 'pending' },
  { id: 'r5', name: 'IMG_4821.HEIC',            size: '3.1 MB', kind: 'img', domain: 'unknown',  entity: '—', source: 'other',                dest: 'raw/inbox/unclassified/', conf: 'Low', reason: 'No readable text · cannot classify confidently', status: 'review' },
  { id: 'r6', name: 'invoice-aws-may.pdf',      size: '120 KB', kind: 'pdf', domain: 'business', entity: 'Tutoring SaaS', source: 'finance',     dest: 'raw/business/Tutoring SaaS/finance/', conf: 'Medium', reason: 'Finance doc — flagged for review before routing', status: 'review' },
  { id: 'r7', name: 'ESC203-team-charter.docx', size: '38 KB',  kind: 'doc', domain: 'course',   entity: 'ESC203', source: 'assignment',       dest: 'raw/courses/ESC203/assignments/', conf: 'High', reason: 'Course code + "team charter" deliverable', status: 'pending' },
];

// --- conversation transcript for the agent cockpit ---
window.CONVERSATION = [
  { who: 'user',  text: 'What\'s the state of my Brain UI project and what should I do next?' },
  { who: 'agent', text: 'Brain UI is your active project. The repo at brain-ui has 3 open escalations — one in progress (Research → Obsidian writer, Claude Code). You have 4 raw files staged for it and a Claude session on API gateway design ready to consolidate.\n\nNext best action: review the agent-cockpit build block running now (13:00–15:00), then approve the 4 queued changes — all medium-risk, high confidence.', proposals: ['Approve 4 queued changes', 'Open Brain UI project'] },
  { who: 'user',  text: 'Research the current NemoClaw / OpenShell policy format. Box it to 10 minutes.' },
  { who: 'agent', text: 'Starting a time-boxed research run — 10 min, scope: web + local vault. I\'ll capture sources, extract claims, and bring back a packet with a confidence label and a save-to-Obsidian proposal. I won\'t write anything until you approve.', research: true },
];

// --- live research run ---
window.RESEARCH = {
  query: 'Current NemoClaw / OpenShell policy format & runtime API',
  budget: 10,
  elapsed: 4.2,
  scope: ['web', 'local vault'],
  depth: 'Decision brief',
  sources: [
    { title: 'NVIDIA NeMo Guardrails — config reference', url: 'docs.nvidia.com/nemo', when: 'just now' },
    { title: 'OpenShell policy schema (GitHub)', url: 'github.com/...', when: '1m ago' },
    { title: 'Sandbox runtime modes — discussion', url: 'forum...', when: '2m ago' },
  ],
  claims: 3,
  confidence: 'Medium',
  gaps: ['Exact runtime API surface unverified', 'Windows install path not confirmed'],
};

// --- nav model ---
window.NAV = [
  { group: 'Operate', items: [
    { id: 'dashboard',  label: 'Dashboard',  glyph: 'grid' },
    { id: 'agent',      label: 'Local Agent', glyph: 'sphere' },
    { id: 'research',   label: 'Research',    glyph: 'search' },
  ]},
  { group: 'Intake', items: [
    { id: 'inbox',      label: 'Raw Inbox',   glyph: 'inbox', badge: 7 },
    { id: 'consolidate',label: 'AI Consolidation', glyph: 'merge' },
    { id: 'calendar',   label: 'Calendar',    glyph: 'cal', badge: 3 },
    { id: 'tasks',      label: 'Tasks',       glyph: 'check' },
  ]},
  { group: 'Work', items: [
    { id: 'projects',   label: 'Projects',    glyph: 'cube' },
    { id: 'hackathons', label: 'Hackathons',  glyph: 'flag' },
    { id: 'courses',    label: 'Courses',     glyph: 'book' },
    { id: 'business',   label: 'Business',    glyph: 'chart' },
    { id: 'resume',     label: 'Resume Pipeline', glyph: 'doc' },
    { id: 'backfill',   label: 'Backfill',    glyph: 'layers' },
  ]},
  { group: 'Control', items: [
    { id: 'escalation', label: 'Escalation Queue', glyph: 'arrow-up', badge: 3 },
    { id: 'safety',     label: 'Tool Safety',  glyph: 'shield' },
    { id: 'settings',   label: 'Settings',     glyph: 'gear' },
  ]},
];
