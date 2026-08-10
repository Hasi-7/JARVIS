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

// ── NemoClaw/OpenShell policy inspection display helpers ────────────────────────

export function policyStatusLabel(status: string): string {
  switch (status) {
    case 'loaded':         return 'Loaded for inspection';
    case 'not_configured': return 'Not configured';
    case 'missing':        return 'File missing';
    case 'unreadable':     return 'Unreadable';
    case 'invalid':        return 'Invalid';
    case 'error':          return 'Error';
    default:               return status;
  }
}

export function policyStatusTone(status: string): RuntimeTone {
  if (status === 'loaded') return 'green';
  if (status === 'invalid' || status === 'unreadable' || status === 'missing') return 'amber';
  if (status === 'error') return 'red';
  return 'grey';
}

// Tri-state capability rendering: allowed / blocked / unknown (never implies allowed).
export function capabilityLabel(v: boolean | null | undefined): string {
  if (v === true) return 'Allowed';
  if (v === false) return 'Blocked';
  return 'Unknown';
}

export function capabilityTone(v: boolean | null | undefined): RuntimeTone {
  if (v === true) return 'amber';   // declared-allowed is noteworthy, but still not wired
  if (v === false) return 'grey';
  return 'grey';
}

// A compact one-line policy state for the Dashboard runtime card.
export function policyDashboardLine(status: string): string {
  switch (status) {
    case 'loaded':         return 'Loaded for inspection';
    case 'invalid':        return 'Invalid';
    case 'unreadable':     return 'Unreadable';
    case 'missing':        return 'File missing';
    case 'error':          return 'Error';
    default:               return 'Not configured';
  }
}

// Required read-only copy shown wherever the policy panel appears.
export const POLICY_COPY = {
  readOnly: 'Policy inspection is read-only. It does not enforce policy or enable runtime actions.',
  disabled: 'Capabilities remain disabled until the runtime bridge is implemented separately.',
};

// ── guardrail readiness display helpers (read-only correlation) ─────────────────

export function readinessStatusLabel(status: string): string {
  switch (status) {
    case 'ready_for_bridge_design': return 'Ready for bridge design';
    case 'partially_ready':         return 'Partial';
    case 'not_ready':               return 'Not ready';
    case 'error':                   return 'Error';
    default:                        return status;
  }
}

export function readinessStatusTone(status: string): RuntimeTone {
  if (status === 'ready_for_bridge_design') return 'green';
  if (status === 'partially_ready') return 'amber';
  if (status === 'error') return 'red';
  return 'grey';
}

// Compact one-word-ish state for the Dashboard runtime card.
export function readinessDashboardLine(status: string): string {
  switch (status) {
    case 'ready_for_bridge_design': return 'Ready for bridge design';
    case 'partially_ready':         return 'Partial';
    case 'error':                   return 'Error';
    default:                        return 'Not ready';
  }
}

// Required read-only copy shown wherever the readiness panel appears.
export const READINESS_COPY = {
  informational: 'Guardrail readiness is informational only. It does not enable OpenClaw, browser, computer-use, MCP, or Gmail actions.',
  notExecution: 'Ready for bridge design does not mean ready for execution.',
};

// ── runtime bridge contract validator display helpers (dry-run only) ────────────

export function bridgeStatusLabel(status: string): string {
  switch (status) {
    case 'validated':       return 'Schema acceptable';
    case 'blocked':         return 'Blocked';
    case 'blocked_by_mode': return 'Blocked by mode';
    case 'error':           return 'Error';
    default:                return status;
  }
}

export function bridgeStatusTone(status: string): RuntimeTone {
  if (status === 'validated') return 'green';
  if (status === 'blocked' || status === 'blocked_by_mode') return 'amber';
  if (status === 'error') return 'red';
  return 'grey';
}

export function riskTone(risk: string): RuntimeTone {
  if (risk === 'high') return 'red';
  if (risk === 'medium') return 'amber';
  if (risk === 'low') return 'grey';
  return 'grey';
}

// Recognized future action kinds for the validator dropdown (mirrors the backend).
export const BRIDGE_ACTION_KINDS = [
  'browser.open', 'browser.search', 'browser.read_page',
  'computer.click', 'computer.type', 'computer.screenshot',
  'mcp.call', 'gmail.search', 'gmail.read', 'calendar.read',
  'vault.read', 'vault.write',
  'brain.status', 'brain.raw_status', 'brain.vault_path',
  'unknown',
];

// Required read-only copy shown on the validator panel.
export const BRIDGE_COPY = {
  dryRun: 'This validates a future runtime bridge request. It does not call NemoClaw/OpenShell or execute the action.',
  notApproval: 'A valid bridge request is not an approval to run it.',
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
