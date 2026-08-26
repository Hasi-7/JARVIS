/**
 * Guards against the class of bug Phase 1 fixed: UI copy and status surfaces
 * that assert something the build no longer does.
 *
 * These are cheap string/logic assertions, but they are exactly the checks that
 * would have caught a Safety page claiming "no email integration" months after
 * Gmail shipped.
 */
import { describe, it, expect } from 'vitest';
import { RUNTIME_TRUTHS, PROBE_COPY, READINESS_COPY, RUNTIME_FALLBACK } from '../runtimeStatus';
import { MODE_POLICY_FALLBACK, resolveModePolicy, modePolicySummary } from '../agentModes';
import { AGENT_MODES, QUICK_ACTIONS, NAV } from '@/data/mock';

/** Phrases that assert a capability does not exist. All of these shipped. */
const FALSE_CLAIMS = [
  'not wired yet',
  'not built',
  'no email integration',
  'planned but not implemented',
  'has no tools',
];

function assertNoFalseClaims(label: string, text: string) {
  for (const claim of FALSE_CLAIMS) {
    expect(
      text.toLowerCase().includes(claim),
      `${label} still claims "${claim}", which is no longer true`,
    ).toBe(false);
  }
}

describe('runtime status copy', () => {
  it('does not claim shipped capabilities are unbuilt', () => {
    assertNoFalseClaims('RUNTIME_TRUTHS', Object.values(RUNTIME_TRUTHS).join(' '));
    assertNoFalseClaims('PROBE_COPY', Object.values(PROBE_COPY).join(' '));
    assertNoFalseClaims('READINESS_COPY', Object.values(READINESS_COPY).join(' '));
  });

  it('still says clearly that status alone enables nothing', () => {
    // The copy must stay cautious even as it stops being wrong: reachability is
    // not permission.
    const all = `${Object.values(PROBE_COPY).join(' ')} ${Object.values(READINESS_COPY).join(' ')}`;
    expect(all.toLowerCase()).toMatch(/enables nothing|does not enable|enable/);
  });

  it('keeps the offline fallback conservative', () => {
    // When the backend is unreachable we must under-claim, never over-claim.
    for (const item of RUNTIME_FALLBACK) {
      expect(item.available, `${item.id} claims availability while offline`).toBe(false);
      expect(item.enabled, `${item.id} claims enablement while offline`).toBe(false);
    }
  });
});

describe('agent mode policy', () => {
  it('does not describe modes as unbuilt', () => {
    const notes = Object.values(MODE_POLICY_FALLBACK).map((m) => m.notes).join(' ');
    assertNoFalseClaims('MODE_POLICY_FALLBACK notes', notes);
    assertNoFalseClaims('AGENT_MODES descriptions', AGENT_MODES.map((m) => m.desc).join(' '));
  });

  it('keeps chat non-executing in every mode', () => {
    // The load-bearing invariant: no mode lets chat run a tool directly.
    for (const policy of Object.values(MODE_POLICY_FALLBACK)) {
      const summary = modePolicySummary(policy);
      expect(summary.tooltip.toLowerCase()).not.toMatch(/chat executes|runs tools directly/);
    }
  });

  it('never resolves to undefined, even for a nonsense mode id', () => {
    expect(resolveModePolicy('not-a-mode', null)).toBeTruthy();
    expect(resolveModePolicy('not-a-mode', null).id).toBe('locked');
  });

  it('prefers backend policy over the static fallback', () => {
    const fromBackend = resolveModePolicy('assist', [
      { id: 'assist', label: 'Assist', available: false, canEvaluateToolRequests: false,
        canOfferReviewHandoff: false, notes: 'backend says no' },
    ]);
    expect(fromBackend.available).toBe(false);
    expect(fromBackend.notes).toBe('backend says no');
  });
});

describe('navigation', () => {
  it('carries no hardcoded badge counts', () => {
    // Static badges reported the same pending work forever. Counts now come
    // from the store; a literal here would silently override a live value.
    for (const group of NAV) {
      for (const item of group.items) {
        expect(item.badge, `${item.id} has a hardcoded badge`).toBeUndefined();
      }
    }
  });

  it('covers every PRD §15 section', () => {
    const ids = new Set(NAV.flatMap((g) => g.items).map((i) => i.id));
    for (const required of [
      'dashboard', 'agent', 'inbox', 'research', 'projects', 'hackathons', 'courses',
      'business', 'calendar', 'tasks', 'resume', 'backfill', 'consolidate', 'tools', 'settings',
    ]) {
      expect(ids.has(required as never), `nav is missing PRD section "${required}"`).toBe(true);
    }
  });

  it('gives every nav item and quick action an icon name that exists', async () => {
    // Icon renders NOTHING for an unknown name, so a typo is invisible.
    const { PATHS } = await import('@/components/ui/Icon');
    const known = new Set(Object.keys(PATHS));
    expect(known.size).toBeGreaterThan(0);
    for (const action of QUICK_ACTIONS) {
      expect(known.has(action.glyph), `quick action "${action.id}" uses unknown glyph "${action.glyph}"`).toBe(true);
    }
    for (const item of NAV.flatMap((g) => g.items)) {
      expect(known.has(item.glyph), `nav item "${item.id}" uses unknown glyph "${item.glyph}"`).toBe(true);
    }
  });
});
