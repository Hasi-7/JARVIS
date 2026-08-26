// Shared agent-mode policy helpers (Global Agent Mode Display v0).
//
// The selected agent mode is global app state (`useAppStore().agentMode`). The
// backend enforces what each mode allows and exposes it via GET /api/agent/modes.
// These helpers resolve a frontend mode id to its backend policy, with a static
// fallback so the app stays honest when the backend is unreachable.
//
// Mirrors backend/app/agent_modes.py. Nothing here executes anything — display only.

import type { AgentModePolicy } from '@/lib/api';

// Map a frontend mode id to the backend canonical mode id.
export function toBackendMode(id: string): string {
  if (id === 'manual') return 'locked';
  if (id === 'computer') return 'computer_use';
  return id;
}

// Static fallback policy so the UI stays honest when the backend is unreachable
// (the frontend works without the backend). Mirrors backend/app/agent_modes.py.
export const MODE_POLICY_FALLBACK: Record<string, AgentModePolicy> = {
  locked:       { id: 'locked',       label: 'Locked',       available: true,  canEvaluateToolRequests: false, canOfferReviewHandoff: false, notes: 'Agent tools disabled. Manual UI pages still work. No tool requests are accepted from chat.' },
  observe:      { id: 'observe',      label: 'Observe',      available: true,  canEvaluateToolRequests: false, canOfferReviewHandoff: false, notes: 'Chat only. Structured tool requests are blocked.' },
  draft:        { id: 'draft',        label: 'Draft',        available: true,  canEvaluateToolRequests: true,  canOfferReviewHandoff: false, notes: 'Tool requests may be evaluated, but nothing executes and no review handoff is offered.' },
  assist:       { id: 'assist',       label: 'Assist',       available: true,  canEvaluateToolRequests: true,  canOfferReviewHandoff: true,  notes: 'Safe-local requests may be reviewed in Tool Connections. Execution remains manual.' },
  research:     { id: 'research',     label: 'Research',     available: true,  canEvaluateToolRequests: true,  canOfferReviewHandoff: false, notes: 'Structured tool requests are evaluated only. Browsing runs from the Research page, inside the sandbox, through the approval queue.' },
  escalation:   { id: 'escalation',   label: 'Escalation',   available: true,  canEvaluateToolRequests: true,  canOfferReviewHandoff: false, notes: 'Handoff/escalation discussion. Tool requests are evaluated only.' },
  computer_use: { id: 'computer_use', label: 'Computer-Use', available: false, canEvaluateToolRequests: false, canOfferReviewHandoff: false, notes: 'Not selectable from chat. Computer-use sessions start from the Browser / Computer Use page via the approval queue, and need their own kill switch.' },
};

// Resolve the policy for a frontend mode id, preferring backend-fetched data and
// falling back to the static copy (offline/degraded). Never returns undefined.
export function resolveModePolicy(
  frontendId: string,
  fetched: AgentModePolicy[] | null,
): AgentModePolicy {
  const backendId = toBackendMode(frontendId);
  const fromBackend = fetched?.find((m) => m.id === backendId);
  return fromBackend ?? MODE_POLICY_FALLBACK[backendId] ?? MODE_POLICY_FALLBACK.locked;
}

// Compact human-readable policy summary for badges/cards.
export interface ModePolicySummary {
  evaluation:  string;   // 'Allowed' | 'Blocked' | 'Unavailable'
  reviewHandoff: string; // 'Safe-local only' | 'Disabled'
  execution:   string;   // always disabled from chat
  tooltip:     string;   // one-line copy for a badge tooltip
}

export function modePolicySummary(policy: AgentModePolicy): ModePolicySummary {
  const evaluation = !policy.available
    ? 'Unavailable'
    : policy.canEvaluateToolRequests ? 'Allowed' : 'Blocked';
  const reviewHandoff = policy.canOfferReviewHandoff ? 'Safe-local only' : 'Disabled';

  let tooltip: string;
  if (!policy.available) {
    tooltip = `${policy.label} is not selectable from chat; it is driven from its own page.`;
  } else if (policy.canEvaluateToolRequests) {
    tooltip = policy.canOfferReviewHandoff
      ? 'Evaluates tool requests. Safe-local review handoff is available. Chat does not execute tools.'
      : 'Evaluates tool requests. No review handoff. Chat does not execute tools.';
  } else {
    tooltip = 'Chat only. Structured tool requests are blocked. Chat does not execute tools.';
  }

  return {
    evaluation,
    reviewHandoff,
    execution: 'Disabled',
    tooltip,
  };
}

// Truths shown in the global / Dashboard mode display.
export const MODE_TRUTHS = [
  'Agent tools are mode-gated by backend policy.',
  'No mode executes tools from chat.',
  'Safe-local execution remains manual in Tool Connections.',
];
