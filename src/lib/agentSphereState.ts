/**
 * Derive the agent sphere state from what the system is ACTUALLY doing.
 *
 * PRD §17 defines thirteen sphere states and §4.7 requires "real agent state,
 * not fake AI theater". Only four were ever set — idle, thinking, speaking and
 * blocked — so a running research session, a live computer-use session, a queue
 * of pending approvals and Locked mode were all invisible.
 *
 * The resolver is pure so it can be tested without a store, a timer, or a DOM.
 */
import type { AgentStateKey } from '@/types';

export interface AgentActivity {
  /** True while a chat turn is streaming. */
  generating?: boolean;
  /** True while tokens are arriving (as opposed to waiting on first token). */
  speaking?: boolean;
  /** A computer-use session is active on the real desktop. */
  computerUseActive?: boolean;
  /** A time-boxed research session is running. */
  researchActive?: boolean;
  /** A research session currently has a page open / is fetching. */
  browserActive?: boolean;
  /** Count of approvals waiting on the operator. */
  pendingApprovals?: number;
  /** The last action was refused by policy. */
  blocked?: boolean;
  /** Canonical agent mode id (backend spelling). */
  mode?: string;
}

/**
 * Precedence matters more than the individual mappings here.
 *
 * Computer-use outranks everything: when something is driving the real desktop,
 * that is the single most important thing the indicator can communicate, and it
 * must not be masked by a chat turn happening at the same time. `blocked` comes
 * next because a refusal the user does not notice is a refusal they will repeat.
 * Locked sits below the live states so an active session is never hidden behind
 * a mode label — being in Locked mode does not stop an already-running session.
 */
export function resolveAgentState(activity: AgentActivity): AgentStateKey {
  if (activity.computerUseActive) return 'computeruse';
  if (activity.blocked) return 'blocked';
  if (activity.browserActive) return 'browser';
  if (activity.researchActive) return 'researching';
  if (activity.speaking) return 'speaking';
  if (activity.generating) return 'thinking';
  if ((activity.pendingApprovals ?? 0) > 1) return 'batch';
  if ((activity.pendingApprovals ?? 0) === 1) return 'pending';
  if (activity.mode === 'locked') return 'locked';
  return 'idle';
}
