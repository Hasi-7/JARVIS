export type AgentStateKey =
  | 'idle' | 'listening' | 'thinking' | 'speaking'
  | 'researching' | 'browser' | 'computeruse'
  | 'pending' | 'batch' | 'escalation'
  | 'blocked' | 'guarded' | 'locked';

export type AgentTone = 'live' | 'amber' | 'red' | 'violet' | 'green' | 'grey';

export type SphereVariant = 'orb' | 'rings' | 'minimal';

export type AgentModeId = 'manual' | 'observe' | 'draft' | 'assist' | 'research' | 'escalation' | 'computer' | 'locked';

export interface AgentMode {
  id: AgentModeId;
  label: string;
  desc: string;
}

export interface AgentStateInfo {
  label: string;
  tone: AgentTone;
  blurb: string;
}

export type RouteId =
  | 'dashboard' | 'agent' | 'research'
  | 'inbox' | 'consolidate' | 'email' | 'calendar' | 'tasks' | 'proposals'
  | 'projects' | 'hackathons' | 'courses' | 'business' | 'resume' | 'backfill'
  | 'computeruse' | 'escalation' | 'tools' | 'safety' | 'settings';

export interface NavItem {
  id: RouteId;
  label: string;
  glyph: string;
  badge?: number;
}

export interface NavGroup {
  group: string;
  items: NavItem[];
}

export type SystemState = 'ready' | 'idle' | 'partial' | 'disabled' | 'blocked';

export interface SystemService {
  state: SystemState;
  label: string;
  detail: string;
  // Optional override for the right-side status text. When omitted, the raw
  // `state` is shown. Used to display honest copy like "Not wired" for runtimes
  // that are planned in the PRD but not implemented yet.
  statusLabel?: string;
}

export interface SystemStatus {
  vault: string;
  brainCmd: string;
  openclaw: SystemService;
  nemoclaw: SystemService;
  browser: SystemService;
  computer: SystemService;
  model: SystemService;
  mcp: SystemService;
}

export interface QuickAction {
  id: string;
  label: string;
  glyph: string;
  group: string;
  cmd?: string;
}

export interface TodayBlock {
  time: string;
  dur: string;
  title: string;
  tag: string;
  done: boolean;
  now?: boolean;
}

export interface Today {
  date: string;
  focus: string;
  blocks: TodayBlock[];
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'disabled';
export type ConfLevel = 'Low' | 'Medium' | 'High';

export interface Approval {
  id: string;
  type: string;
  risk: RiskLevel;
  conf: ConfLevel;
  title: string;
  files: number;
  reason: string;
}

export interface Escalation {
  id: string;
  task: string;
  agent: string;
  reason: string;
  repo: string;
  status: string;
}

export type AiSource = 'claude' | 'chatgpt' | 'opencode';

export interface ConsolidatedItem {
  id: string;
  source: AiSource;
  title: string;
  dest: string;
  when: string;
  items: string;
}

export interface CmdLogEntry {
  cmd: string;
  ok: boolean;
  at: string;
  out: string;
}

export interface PaletteItem {
  kind: 'nav' | 'cmd' | 'act';
  id: string;
  label: string;
  group: string;
  glyph: string;
}
