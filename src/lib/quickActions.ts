/**
 * One resolver for quick actions (PRD §16).
 *
 * This logic used to exist twice — DashboardPage and AppShell's ⌘K palette —
 * and both fell through to a `"(not wired yet)"` toast for the three entity
 * creators, even though `new-project` / `new-course` / `new-hackathon` are all
 * in the backend allowlist. Having it in one place is what stops the two copies
 * drifting apart again.
 */
import type { RouteId } from '@/types';

/** Quick actions that map straight onto an allowlisted brain subcommand. */
export const BRAIN_ACTION_MAP: Record<string, string> = {
  today:     'today',
  weekly:    'weekly',
  syncraw:   'sync-raw',
  calexport: 'calendar-export',
  calopen:   'calendar-open',
  backup:    'backup',
  lint:      'lint',
};

/** Quick actions that are pure navigation. */
export const NAV_ACTION_MAP: Record<string, RouteId> = {
  ask:          'agent',
  research:     'research',
  consolidate:  'consolidate',
  upload:       'inbox',
  calcandidates:'calendar',
  checkopenclaw:'tools',
  checkbrowser: 'computeruse',
  checkcomputer:'computeruse',
  checkmcp:     'tools',
  checksafety:  'safety',
};

/** Quick actions that open an entity-creation modal. */
export const ENTITY_ACTION_MAP: Record<string, 'project' | 'course' | 'hackathon' | 'business'> = {
  newproj:     'project',
  newhack:     'hackathon',
  newcourse:   'course',
  newbusiness: 'business',
};

export type QuickActionResolution =
  | { kind: 'navigate'; route: RouteId }
  | { kind: 'brain'; command: string }
  | { kind: 'entity'; entity: 'project' | 'course' | 'hackathon' | 'business' }
  | { kind: 'unknown'; id: string };

/**
 * Pure. Returns what a quick-action id means; the caller performs the effect.
 * Kept side-effect-free so it can be unit tested without a store or a DOM.
 */
export function resolveQuickAction(id: string): QuickActionResolution {
  const route = NAV_ACTION_MAP[id];
  if (route) return { kind: 'navigate', route };

  const command = BRAIN_ACTION_MAP[id];
  if (command) return { kind: 'brain', command };

  const entity = ENTITY_ACTION_MAP[id];
  if (entity) return { kind: 'entity', entity };

  return { kind: 'unknown', id };
}
