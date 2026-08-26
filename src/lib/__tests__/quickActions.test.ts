import { describe, it, expect } from 'vitest';
import { resolveQuickAction, BRAIN_ACTION_MAP } from '../quickActions';
import { QUICK_ACTIONS } from '@/data/mock';

describe('resolveQuickAction', () => {
  it('routes navigation actions', () => {
    expect(resolveQuickAction('ask')).toEqual({ kind: 'navigate', route: 'agent' });
    expect(resolveQuickAction('upload')).toEqual({ kind: 'navigate', route: 'inbox' });
  });

  it('routes brain commands', () => {
    expect(resolveQuickAction('today')).toEqual({ kind: 'brain', command: 'today' });
    expect(resolveQuickAction('syncraw')).toEqual({ kind: 'brain', command: 'sync-raw' });
  });

  it('routes the entity creators that used to dead-end in a toast', () => {
    // These three were allowlisted in the backend the whole time, but both the
    // dashboard and the palette fell through to "(not wired yet)".
    expect(resolveQuickAction('newproj')).toEqual({ kind: 'entity', entity: 'project' });
    expect(resolveQuickAction('newhack')).toEqual({ kind: 'entity', entity: 'hackathon' });
    expect(resolveQuickAction('newcourse')).toEqual({ kind: 'entity', entity: 'course' });
  });

  it('reports genuinely unknown ids rather than guessing', () => {
    expect(resolveQuickAction('nope')).toEqual({ kind: 'unknown', id: 'nope' });
  });

  it('resolves EVERY declared quick action', () => {
    // The regression guard: a quick action that no branch handles renders a
    // button that silently does nothing.
    const unresolved = QUICK_ACTIONS
      .map((a) => a.id)
      .filter((id) => resolveQuickAction(id).kind === 'unknown');
    expect(unresolved).toEqual([]);
  });

  it('only maps brain commands that the backend allowlist accepts', () => {
    // Mirrors backend/app/security.py ALLOWED_COMMANDS. An entry here that the
    // backend refuses would surface to the user as a runtime error.
    const backendAllowlist = new Set([
      'doctor', 'status', 'vault-path', 'today', 'weekly', 'raw-status', 'sync-raw',
      'calendar-export', 'calendar-open', 'new-project', 'new-course', 'new-hackathon',
      'project-closeout', 'new-repo-scaffold', 'archive-hackathon', 'backup', 'lint',
    ]);
    for (const command of Object.values(BRAIN_ACTION_MAP)) {
      expect(backendAllowlist.has(command), `${command} is not in the backend allowlist`).toBe(true);
    }
  });
});
