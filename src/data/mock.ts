import type {
  AgentStateInfo,
  AgentStateKey,
  AgentMode,
  QuickAction,
  Today,
  Approval,
  Escalation,
  ConsolidatedItem,
  CmdLogEntry,
  NavGroup,
} from '@/types';

// Mock config — these values are placeholders until the backend is connected.
// Real values will be resolved from:
//   vault path  →  brain vault-path (CLI)
//   brain.cmd   →  app config endpoint
export const APP_CONFIG = {
  vaultPath: 'D:\\Hasnain\\Obsidian\\AI-Command-Center',
  brainCmd:  'D:\\Hasnain\\Personal\\bin\\brain.cmd',
} as const;

export const AGENT_STATES: Record<AgentStateKey, AgentStateInfo> = {
  idle:        { label: 'Idle',             tone: 'live',   blurb: 'Resident · breathing' },
  listening:   { label: 'Listening',        tone: 'live',   blurb: 'Capturing input' },
  thinking:    { label: 'Thinking',         tone: 'live',   blurb: 'Local model reasoning' },
  speaking:    { label: 'Speaking',         tone: 'live',   blurb: 'Responding' },
  researching: { label: 'Researching',      tone: 'live',   blurb: 'Browser harness · time-boxed' },
  browser:     { label: 'Browser active',   tone: 'live',   blurb: 'Operating a page' },
  computeruse: { label: 'Computer use',     tone: 'live',   blurb: 'Driving approved UI' },
  pending:     { label: 'Tool request',     tone: 'amber',  blurb: '1 action awaiting approval' },
  batch:       { label: 'Batch approval',   tone: 'amber',  blurb: '6 changes queued' },
  escalation:  { label: 'Escalation ready', tone: 'violet', blurb: 'Handoff prepared' },
  blocked:     { label: 'Blocked',          tone: 'red',    blurb: 'Action denied by policy' },
  guarded:     { label: 'Guarded',          tone: 'green',  blurb: 'NemoClaw / OpenShell active' },
  locked:      { label: 'Locked',           tone: 'grey',   blurb: 'Tools disabled · manual' },
};

export const AGENT_MODES: AgentMode[] = [
  { id: 'manual',     label: 'Manual',       desc: 'You drive. Agent tools off — no tool requests.' },
  { id: 'observe',    label: 'Observe',      desc: 'Chat only. Structured tool requests are blocked.' },
  { id: 'draft',      label: 'Draft',        desc: 'Tool requests may be evaluated. Nothing executes.' },
  { id: 'assist',     label: 'Assist',       desc: 'Safe-local requests reviewable in Tool Connections. Execution stays manual.' },
  { id: 'research',   label: 'Research',     desc: 'Tool requests evaluated only. Browsing runs from the Research page via the approval queue.' },
  { id: 'escalation', label: 'Escalation',   desc: 'Handoff discussion. Tool requests evaluated only.' },
  { id: 'computer',   label: 'Computer Use', desc: 'Driven from its own page, not from chat. Needs its own kill switch.' },
  { id: 'locked',     label: 'Locked',       desc: 'All agent tools disabled. Manual UI works.' },
];

export const QUICK_ACTIONS: QuickAction[] = [
  { id: 'ask',         label: 'Ask Agent',          glyph: 'spark',  group: 'Agent' },
  { id: 'research',    label: 'Research Topic',     glyph: 'search', group: 'Agent' },
  { id: 'consolidate', label: 'Consolidate AI Work', glyph: 'merge', group: 'Agent' },
  { id: 'today',       label: 'Run brain today',    glyph: 'sun',    group: 'Brain CLI', cmd: 'brain today' },
  { id: 'weekly',      label: 'Run brain weekly',   glyph: 'cal',    group: 'Brain CLI', cmd: 'brain weekly' },
  { id: 'syncraw',     label: 'Sync Raw',           glyph: 'sync',   group: 'Brain CLI', cmd: 'brain sync-raw' },
  { id: 'calexport',   label: 'Export Calendar',    glyph: 'cal',    group: 'Brain CLI', cmd: 'brain calendar-export' },
  { id: 'upload',      label: 'Upload Raw File',    glyph: 'upload', group: 'Intake' },
  { id: 'calopen',     label: 'Open Calendar',      glyph: 'cal',    group: 'Brain CLI', cmd: 'brain calendar-open' },
  { id: 'calcandidates', label: 'Calendar Candidates', glyph: 'check', group: 'Intake' },
  { id: 'newproj',     label: 'New Project',        glyph: 'plus',   group: 'Create', cmd: 'brain new-project' },
  { id: 'newhack',     label: 'New Hackathon',      glyph: 'plus',   group: 'Create', cmd: 'brain new-hackathon' },
  { id: 'newcourse',   label: 'New Course',         glyph: 'plus',   group: 'Create', cmd: 'brain new-course' },
  { id: 'newbusiness', label: 'New Business Area',  glyph: 'chart',  group: 'Create' },
  // PRD §16 "Check …" actions. They navigate to the page that reports real
  // status rather than pretending to run a probe from here.
  { id: 'checkopenclaw', label: 'Check OpenClaw',       glyph: 'sphere', group: 'Status' },
  { id: 'checkbrowser',  label: 'Check Browser Harness', glyph: 'search', group: 'Status' },
  { id: 'checkcomputer', label: 'Check Computer Use',    glyph: 'grid',   group: 'Status' },
  { id: 'checkmcp',      label: 'Check MCP Connections', glyph: 'layers', group: 'Status' },
  { id: 'checksafety',   label: 'Tool Safety + Logs',    glyph: 'shield', group: 'Status' },
];

export const TODAY: Today = {
  date:  'Fri · May 30',
  focus: 'MAT292 problem set 6 + Brain UI handoff',
  blocks: [
    { time: '09:30', dur: '90m',  title: 'MAT292 — Laplace transforms PS6',          tag: 'course',    done: true  },
    { time: '11:30', dur: '45m',  title: 'Stand-up notes → vault',                   tag: 'ops',       done: true  },
    { time: '13:00', dur: '120m', title: 'Brain UI — agent cockpit build',            tag: 'project',   done: false, now: true },
    { time: '15:30', dur: '60m',  title: 'Review research packet: NemoClaw policy',  tag: 'research',  done: false },
    { time: '17:00', dur: '45m',  title: 'Hack the North — submission draft',         tag: 'hackathon', done: false },
  ],
};

export const APPROVALS: Approval[] = [
  {
    id: 'ap1', type: 'file_route', risk: 'medium', conf: 'High',
    title: 'Route 4 lecture PDFs → courses/MAT292/lectures', files: 4,
    reason: 'Filenames + headers match MAT292 lecture series',
  },
  {
    id: 'ap2', type: 'chat_consolidation', risk: 'medium', conf: 'Medium',
    title: 'Save Claude session "API gateway design" → projects/Brain UI', files: 1,
    reason: 'Conversation references repo brain-ui and FastAPI gateway',
  },
  {
    id: 'ap3', type: 'calendar_candidate', risk: 'medium', conf: 'High',
    title: 'Add 3 calendar candidates from PS deadlines', files: 3,
    reason: 'Extracted from Quercus email digest',
  },
  {
    id: 'ap4', type: 'task_add', risk: 'low', conf: 'High',
    title: "Add 5 task rows from today's standup note", files: 5,
    reason: 'Action items detected in standup.md',
  },
];

export const ESCALATIONS: Escalation[] = [
  {
    id: 'es1', task: 'Refactor brain CLI command broker for async', agent: 'Claude Code',
    reason: 'Multi-file change across 14 modules — exceeds local model reliability',
    repo: 'D:\\...\\brain-ui\\backend', status: 'ready',
  },
  {
    id: 'es2', task: 'Backfill closeout: robotics-arm-2024 repo', agent: 'OpenCode',
    reason: 'Large repo synthesis + archive generation',
    repo: 'D:\\...\\robotics-arm-2024', status: 'queued',
  },
  {
    id: 'es3', task: 'Implement Research packet → Obsidian writer', agent: 'Claude Code',
    reason: 'Implementation-ready plan needed from research notes',
    repo: 'D:\\...\\brain-ui', status: 'in-progress',
  },
];

export const CONSOLIDATED: ConsolidatedItem[] = [
  { id: 'c1', source: 'claude',   title: 'API gateway design discussion',  dest: 'raw/chats/claude/',    when: '2h ago',   items: '4 decisions · 2 snippets' },
  { id: 'c2', source: 'chatgpt',  title: 'Laplace transform intuition',    dest: 'raw/courses/MAT292/',  when: 'Yesterday', items: '6 notes · 1 next action' },
  { id: 'c3', source: 'opencode', title: 'Session: vault lint pass',        dest: 'raw/chats/opencode/', when: 'Yesterday', items: '3 fixes · 1 task' },
];

export const CMD_LOG: CmdLogEntry[] = [
  { cmd: 'brain status',   ok: true,  at: '13:02', out: 'vault OK · 1,284 notes · 7 raw pending · last backup 04:00' },
  { cmd: 'brain sync-raw', ok: true,  at: '12:41', out: 'synced 7 files · 0 conflicts' },
  { cmd: 'brain doctor',   ok: true,  at: '09:15', out: 'all checks passed (12/12)' },
];

// No `badge` values here: badges are live counts resolved in Sidebar from the
// store. Hardcoding them made the sidebar report stale work every session.
export const NAV: NavGroup[] = [
  {
    group: 'Operate',
    items: [
      { id: 'dashboard', label: 'Dashboard',  glyph: 'grid'   },
      { id: 'agent',     label: 'Local Agent', glyph: 'sphere' },
      { id: 'research',  label: 'Research',   glyph: 'search' },
      { id: 'computeruse', label: 'Browser / Computer Use', glyph: 'grid' },
    ],
  },
  {
    group: 'Intake',
    items: [
      { id: 'inbox',      label: 'Raw Inbox',       glyph: 'inbox' },
      { id: 'proposals',  label: 'Proposal Queue',   glyph: 'check' },
      { id: 'consolidate',label: 'AI Consolidation', glyph: 'merge' },
      { id: 'email',      label: 'Email Intake',     glyph: 'inbox' },
      { id: 'calendar',   label: 'Calendar',         glyph: 'cal'   },
      { id: 'tasks',      label: 'Tasks',            glyph: 'check' },
    ],
  },
  {
    group: 'Work',
    items: [
      { id: 'projects',   label: 'Projects',         glyph: 'cube'   },
      { id: 'hackathons', label: 'Hackathons',       glyph: 'flag'   },
      { id: 'courses',    label: 'Courses',          glyph: 'book'   },
      { id: 'business',   label: 'Business',         glyph: 'chart'  },
      { id: 'resume',     label: 'Resume Pipeline',  glyph: 'doc'    },
      { id: 'backfill',   label: 'Backfill',         glyph: 'layers' },
    ],
  },
  {
    group: 'Control',
    items: [
      { id: 'escalation', label: 'Escalation Queue', glyph: 'arrow-up' },
      { id: 'tools',      label: 'Tool Connections', glyph: 'layers'    },
      { id: 'safety',     label: 'Tool Safety',      glyph: 'shield'    },
      { id: 'settings',   label: 'Settings',         glyph: 'gear'      },
    ],
  },
];
