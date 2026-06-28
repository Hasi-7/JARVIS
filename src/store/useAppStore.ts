import { create } from 'zustand';
import type { AgentStateKey, AgentMode, RouteId, CmdLogEntry } from '@/types';

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
import type { AgentStatus, BackendConfig } from '@/lib/api';
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
  setAgentPrefill: (msg: string) => void;
  setAgentConvTarget: (id: string | null) => void;
  setProposalTarget: (t: ProposalTarget | null) => void;
  setToolReviewTarget: (t: ToolReviewTarget | null) => void;
  runBrainCommand: (cmd: string) => Promise<void>;

  setStagedCount: (n: number) => void;
  setPendingProposalCount: (n: number) => void;
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
  agentPrefill: '',
  agentConvTarget: null,
  proposalTarget: null,
  toolReviewTarget: null,
  cmdLog: [],
  stagedCount: 0,
  pendingProposalCount: 0,

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

  setAgentPrefill: (msg) => set({ agentPrefill: msg }),

  setAgentConvTarget: (agentConvTarget) => set({ agentConvTarget }),

  setProposalTarget: (proposalTarget) => set({ proposalTarget }),

  setToolReviewTarget: (toolReviewTarget) => set({ toolReviewTarget }),

  runBrainCommand: async (cmd: string) => {
    const at = nowHHMM();
    get().showToast(`Running brain ${cmd}…`);
    try {
      const result = await api.runBrain(cmd);
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

  addCmdEntry: (entry) => set((s) => ({ cmdLog: [entry, ...s.cmdLog].slice(0, 20) })),

  loadStagedCount: async () => {
    try {
      const [staged, proposals] = await Promise.all([
        api.getStagedFiles(),
        api.getIntakeProposals(),
      ]);
      set({
        stagedCount: staged.files.length,
        pendingProposalCount: proposals.proposals.filter(
          (p) => p.status === 'proposed' || p.status === 'edited'
        ).length,
      });
    } catch {
      // Backend may be down — leave counts unchanged
    }
  },
}));
