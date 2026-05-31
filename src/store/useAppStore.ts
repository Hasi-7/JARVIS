import { create } from 'zustand';
import type { AgentStateKey, AgentMode, RouteId } from '@/types';
import { AGENT_MODES } from '@/data/mock';

interface AppState {
  route: RouteId;
  agentState: AgentStateKey;
  agentMode: AgentMode;
  paletteOpen: boolean;
  toast: string;

  navigate: (route: RouteId) => void;
  setAgentState: (state: AgentStateKey) => void;
  setAgentMode: (mode: AgentMode) => void;
  openPalette: () => void;
  closePalette: () => void;
  showToast: (msg: string) => void;
}

let toastTimer: ReturnType<typeof setTimeout> | null = null;

export const useAppStore = create<AppState>((set) => ({
  route: 'dashboard',
  agentState: 'idle',
  agentMode: AGENT_MODES[3], // Assist
  paletteOpen: false,
  toast: '',

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
}));
