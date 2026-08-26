import { create } from 'zustand';
import type { AgentStateKey, AgentMode, RouteId, CmdLogEntry } from '@/types';

/** Entity kinds that have a "New …" quick action + creation modal. */
export type EntityKind = 'project' | 'course' | 'hackathon' | 'business';

// Deep-link handoff from the Proposal Queue to a source page (selection/highlight only).
export type ProposalTargetSource = 'raw-inbox' | 'chat-consolidation' | 'research' | 'email-intake';
export interface ProposalTarget {
  source: ProposalTargetSource;
  relatedId: string;
}

// Deep-link handoff from an evaluated Local Agent tool request to the Tool
// Connections evaluator/executor (prefill only — never executes during handoff).
export interface ToolReviewTarget {
  tool: string;
  argsSummary?: string;
  reason?: string;
  requestedBy?: string;
  source?: 'agent-chat' | 'agent-tool-request' | 'manual';
  relatedId?: string;
}
import { AGENT_MODES } from '@/data/mock';
import type { AppSettings } from '@/lib/config';
import { loadSettings, saveSettings as persistSettings, clearSettings, DEFAULTS, hasLocalSettings } from '@/lib/config';
import type { AgentStatus, BackendConfig, AgentModePolicy } from '@/lib/api';
import { api } from '@/lib/api';

interface AppState {
  route: RouteId;
  agentState: AgentStateKey;
  agentMode: AgentMode;
  paletteOpen: boolean;
  toast: string;
  settings: AppSettings;

  // Backend connection state
  backendStatus: 'unknown' | 'ok' | 'error';
  backendConfig: BackendConfig | null;

  // Local agent (Ollama) status
  agentStatus: AgentStatus | null;

  // Backend-enforced agent mode policy (GET /api/agent/modes). null until loaded;
  // consumers fall back to a static policy copy when this is null (backend down).
  agentModes: AgentModePolicy[] | null;

  // Prefill for the Local Agent composer (set by Dashboard "Ask the agent")
  agentPrefill: string;

  // Deep-link target: conversation id to open in AgentPage (set by Dashboard
  // Recent AI Work row click). Consumed and cleared by AgentPage on mount.
  agentConvTarget: string | null;

  // Deep-link target from the Proposal Queue → highlight the exact source item.
  // Consumed and cleared by the matching source page (Inbox/Consolidate/Research).
  proposalTarget: ProposalTarget | null;

  // Deep-link target from a Local Agent tool request → Tool Connections evaluator.
  // Consumed and cleared by ToolConnectionsPage on mount (prefill only, no execution).
  toolReviewTarget: ToolReviewTarget | null;

  // Live command log (real output from backend)
  cmdLog: CmdLogEntry[];

  // Count of files currently in the staging inbox
  stagedCount: number;
  /** Live sidebar badge counts. Previously these were hardcoded numbers in NAV
   *  that never changed, which made the sidebar assert stale work every session. */
  calendarPendingCount: number;
  escalationActiveCount: number;
  /** Set by a "New <entity>" quick action; the target page consumes and clears it
   *  so the modal opens exactly once rather than on every visit. */
  entityCreateTarget: EntityKind | null;
  // Count of proposals with status proposed|edited (needs review)
  pendingProposalCount: number;

  navigate: (route: RouteId) => void;
  setAgentState: (state: AgentStateKey) => void;
  setAgentMode: (mode: AgentMode) => void;
  openPalette: () => void;
  closePalette: () => void;
  showToast: (msg: string) => void;
  updateSettings: (s: AppSettings) => void;
  resetSettings: () => void;
  syncConfigToBackend: (s: AppSettings) => Promise<void>;
  checkBackend: () => Promise<void>;
  checkAgentStatus: () => Promise<void>;
  loadAgentModes: () => Promise<void>;
  setAgentPrefill: (msg: string) => void;
  setAgentConvTarget: (id: string | null) => void;
  setProposalTarget: (t: ProposalTarget | null) => void;
  setToolReviewTarget: (t: ToolReviewTarget | null) => void;
  runBrainCommand: (cmd: string, args?: Record<string, string>) => Promise<void>;

  setStagedCount: (n: number) => void;
  setPendingProposalCount: (n: number) => void;
  setEntityCreateTarget: (kind: EntityKind | null) => void;
  consumeEntityCreateTarget: (kind: EntityKind) => boolean;
  addCmdEntry: (entry: CmdLogEntry) => void;
  loadStagedCount: () => Promise<void>;
}

let toastTimer: ReturnType<typeof setTimeout> | null = null;

function nowHHMM(): string {
  return new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false });
}

export const useAppStore = create<AppState>((set, get) => ({
  route: 'dashboard',
  agentState: 'idle',
  agentMode: AGENT_MODES[3], // Assist
  paletteOpen: false,
  toast: '',
  settings: loadSettings(),

  backendStatus: 'unknown',
  backendConfig: null,
  agentStatus: null,
  agentModes: null,
  agentPrefill: '',
  agentConvTarget: null,
  proposalTarget: null,
  toolReviewTarget: null,
  cmdLog: [],
  stagedCount: 0,
  pendingProposalCount: 0,
  calendarPendingCount: 0,
  escalationActiveCount: 0,
  entityCreateTarget: null,

  navigate: (route) => set({ route }),
  setAgentState: (agentState) => set({ agentState }),
  setAgentMode: (agentMode) => set({ agentMode }),
  openPalette: () => set({ paletteOpen: true }),
  closePalette: () => set({ paletteOpen: false }),

  showToast: (msg) => {
    if (toastTimer) clearTimeout(toastTimer);
    set({ toast: msg });
    toastTimer = setTimeout(() => set({ toast: '' }), 2200);
  },

  updateSettings: (s) => {
    persistSettings(s);
    set({ settings: s });
  },

  resetSettings: () => {
    clearSettings();
    set({ settings: { ...DEFAULTS } });
  },

  syncConfigToBackend: async (s: AppSettings) => {
    const updated = await api.updateConfig(s); // throws on failure
    set({ backendConfig: updated, backendStatus: 'ok' });
  },

  checkBackend: async () => {
    try {
      await api.health();
      const backendCfg = await api.config();
      set({ backendStatus: 'ok', backendConfig: backendCfg });

      if (hasLocalSettings()) {
        // Push user's local settings to backend so it uses the same paths.
        try {
          const updated = await api.updateConfig(get().settings);
          set({ backendConfig: updated });
        } catch {
          // Silent — local settings remain valid; backend sync failed
        }
      } else {
        // No local overrides: seed displayed settings from backend config.
        set({
          settings: {
            vaultPath: backendCfg.vaultPath,
            brainCmd: backendCfg.brainCmd,
          },
        });
      }

      // Also probe Ollama/local model while backend is reachable.
      try {
        const agentStatus = await api.getAgentStatus();
        set({ agentStatus });
      } catch {
        // Ollama check failure is non-fatal — backend is still ok
      }
    } catch {
      set({ backendStatus: 'error', backendConfig: null });
    }
  },

  checkAgentStatus: async () => {
    try {
      const agentStatus = await api.getAgentStatus();
      set({ agentStatus });
    } catch (err) {
      set({
        agentStatus: {
          ok: false,
          provider: 'ollama',
          baseUrl: 'http://localhost:11434',
          model: '',
          available: false,
          message: err instanceof Error ? err.message : 'Could not reach backend.',
        },
      });
    }
  },

  loadAgentModes: async () => {
    try {
      const res = await api.getAgentModes();
      set({ agentModes: res.modes });
    } catch {
      // Non-fatal — consumers fall back to the static policy copy. Do not block the app.
    }
  },

  setAgentPrefill: (msg) => set({ agentPrefill: msg }),

  setAgentConvTarget: (agentConvTarget) => set({ agentConvTarget }),

  setProposalTarget: (proposalTarget) => set({ proposalTarget }),

  setToolReviewTarget: (toolReviewTarget) => set({ toolReviewTarget }),

  runBrainCommand: async (cmd: string, args?: Record<string, string>) => {
    const at = nowHHMM();
    get().showToast(`Running brain ${cmd}…`);
    try {
      const result = await api.runBrain(cmd, args);
      const rawOut = result.stdout.trim() || result.stderr.trim() || (result.ok ? 'Done.' : 'Failed.');
      const out = rawOut.split('\n').find((l) => l.trim()) ?? rawOut;
      const entry: CmdLogEntry = { cmd: `brain ${cmd}`, ok: result.ok, at, out };
      set((s) => ({ cmdLog: [entry, ...s.cmdLog].slice(0, 20) }));
      get().showToast(result.ok ? `brain ${cmd} · done` : `brain ${cmd} · failed`);
    } catch (err) {
      const entry: CmdLogEntry = {
        cmd: `brain ${cmd}`,
        ok: false,
        at,
        out: err instanceof Error ? err.message : 'Backend not available.',
      };
      set((s) => ({ cmdLog: [entry, ...s.cmdLog].slice(0, 20) }));
      get().showToast('Backend not reachable.');
    }
  },

  setStagedCount: (n) => set({ stagedCount: n }),

  setPendingProposalCount: (n) => set({ pendingProposalCount: n }),

  setEntityCreateTarget: (kind) => set({ entityCreateTarget: kind }),

  consumeEntityCreateTarget: (kind) => {
    if (get().entityCreateTarget !== kind) return false;
    set({ entityCreateTarget: null });
    return true;
  },

  addCmdEntry: (entry) => set((s) => ({ cmdLog: [entry, ...s.cmdLog].slice(0, 20) })),

  loadStagedCount: async () => {
    // Each source is settled independently: one failing endpoint must not blank
    // every badge, which would read as "no pending work" rather than "unknown".
    const [staged, proposals, summary] = await Promise.allSettled([
      api.getStagedFiles(),
      api.getIntakeProposals(),
      api.getDashboardSummary(),
    ]);
    const next: Partial<AppState> = {};
    if (staged.status === 'fulfilled') next.stagedCount = staged.value.files.length;
    if (proposals.status === 'fulfilled') {
      next.pendingProposalCount = proposals.value.proposals.filter(
        (p) => p.status === 'proposed' || p.status === 'edited'
      ).length;
    }
    if (summary.status === 'fulfilled') {
      next.calendarPendingCount = summary.value.calendar.pending;
      next.escalationActiveCount = summary.value.escalations.active;
    }
    if (Object.keys(next).length > 0) set(next);
  },
}));
