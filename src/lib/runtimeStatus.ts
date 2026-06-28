// Shared helpers for OpenClaw / NemoClaw Runtime Status v0 (read-only display).
//
// Loads GET /api/runtime/status with a safe static fallback so the UI never blocks
// and never falsely shows a runtime as ready. Nothing here launches or executes
// anything — display only.

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeStatusItem } from '@/lib/api';

// ── NemoClaw/OpenShell probe display helpers ────────────────────────────────────

export function probeStatusLabel(status: string): string {
  switch (status) {
    case 'reachable':      return 'Reachable';
    case 'unavailable':    return 'Unavailable';
    case 'not_configured': return 'Not configured';
    case 'error':          return 'Error';
    default:               return status;
  }
}

export function probeStatusTone(status: string): RuntimeTone {
  if (status === 'reachable') return 'green';
  if (status === 'unavailable') return 'amber';
  if (status === 'error') return 'red';
  return 'grey';
}

// Safety copy shown next to the probe control.
export const PROBE_COPY = {
  what: 'This checks whether a configured NemoClaw/OpenShell runtime is reachable. It does not start the runtime or enable browser/computer-use.',
  stillDisabled: 'Browser and computer-use remain disabled until a separate runtime bridge is implemented and explicitly enabled.',
};

// Standing truths required by the PRD / spec wherever runtime status is shown.
export const RUNTIME_TRUTHS = {
  notWired: 'Privileged agent runtimes are not wired yet.',
  browserBlocked: 'Browser and computer-use remain blocked until NemoClaw/OpenShell is available.',
};

// Static fallback mirroring the backend default (no env configured) so a backend-down
// state degrades honestly. The backend is authoritative when reachable.
export const RUNTIME_FALLBACK: RuntimeStatusItem[] = [
  {
    id: 'openclaw', name: 'OpenClaw', status: 'not_configured', available: false, enabled: false,
    requiredFor: ['Resident local agent', 'Agent tool requests (later)'],
    dependsOn: ['nemoclaw_openshell'],
    blocks: ['OpenClaw bridge not wired in this build'],
    configured: { enabledFlag: false, baseUrl: false },
    notes: 'OpenClaw bridge is planned but not wired in this build.',
  },
  {
    id: 'nemoclaw_openshell', name: 'NemoClaw / OpenShell', status: 'not_configured', available: false, enabled: false,
    requiredFor: ['Browser harness', 'Computer-use', 'OpenClaw privileged actions', 'MCP privileged actions'],
    dependsOn: [],
    blocks: ['NemoClaw/OpenShell runtime not configured'],
    configured: { enabledFlag: false, runtimeUrl: false, policyPath: false },
    notes: 'Required runtime guardrail for privileged agent actions. Not wired in this build.',
  },
  {
    id: 'browser_harness', name: 'Browser Harness', status: 'disabled', available: false, enabled: false,
    requiredFor: ['Time-boxed research', 'Source capture (later)'],
    dependsOn: ['nemoclaw_openshell'],
    blocks: ['NemoClaw/OpenShell runtime unavailable', 'Browser harness not enabled (ENABLE_BROWSER_HARNESS)'],
    configured: { enabledFlag: false },
    notes: 'Blocked until NemoClaw/OpenShell is available.',
  },
  {
    id: 'computer_use', name: 'Computer Use', status: 'disabled', available: false, enabled: false,
    requiredFor: ['Supervised UI operation (later)'],
    dependsOn: ['nemoclaw_openshell'],
    blocks: ['NemoClaw/OpenShell runtime unavailable', 'Computer-use not enabled (ENABLE_COMPUTER_USE)'],
    configured: { enabledFlag: false },
    notes: 'Blocked until NemoClaw/OpenShell is available.',
  },
  {
    id: 'mcp_gateway', name: 'MCP Gateway', status: 'not_configured', available: false, enabled: false,
    requiredFor: ['Obsidian MCP', 'Gmail MCP', 'Calendar / Drive tools (later)'],
    dependsOn: ['nemoclaw_openshell'],
    blocks: ['Runtime guardrail (NemoClaw/OpenShell) unavailable for privileged actions', 'MCP gateway not enabled (ENABLE_MCP_GATEWAY)'],
    configured: { enabledFlag: false },
    notes: 'Not wired. Privileged MCP actions require the Permission Gateway plus the runtime guardrail.',
  },
];

export type RuntimeTone = 'green' | 'amber' | 'red' | 'grey';

// A runtime is "blocked" (vs merely off) when it is disabled and has blocker reasons.
export function isBlocked(item: RuntimeStatusItem): boolean {
  return item.status === 'disabled' && item.blocks.length > 0;
}

export function runtimeStatusLabel(item: RuntimeStatusItem): string {
  if (item.available) return 'Available';
  if (isBlocked(item)) return 'Blocked';
  switch (item.status) {
    case 'unavailable':    return 'Unavailable';
    case 'not_configured': return 'Not configured';
    case 'disabled':       return 'Disabled';
    case 'planned':        return 'Planned';
    case 'error':          return 'Error';
    default:               return item.status;
  }
}

export function runtimeStatusTone(item: RuntimeStatusItem): RuntimeTone {
  if (item.available) return 'green';
  if (item.status === 'error') return 'red';
  if (item.status === 'unavailable' || isBlocked(item)) return 'amber';
  return 'grey';
}

// Shared loader. Returns the backend list when reachable, else the static fallback,
// with `degraded` true so the UI can say so. Never throws.
export interface RuntimeStatusState {
  items: RuntimeStatusItem[];
  loading: boolean;
  degraded: boolean;   // backend unreachable → showing fallback copy
}

export function useRuntimeStatus(): RuntimeStatusState {
  const [items, setItems] = useState<RuntimeStatusItem[]>(RUNTIME_FALLBACK);
  const [loading, setLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    let alive = true;
    api.getRuntimeStatus()
      .then((res) => { if (alive) { setItems(res.items); setDegraded(false); } })
      .catch(() => { if (alive) { setItems(RUNTIME_FALLBACK); setDegraded(true); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { items, loading, degraded };
}
