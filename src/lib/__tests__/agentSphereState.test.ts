import { describe, it, expect } from 'vitest';
import { resolveAgentState } from '../agentSphereState';

describe('resolveAgentState', () => {
  it('shows idle when nothing is happening', () => {
    expect(resolveAgentState({})).toBe('idle');
  });

  it('surfaces computer-use above everything else', () => {
    // Something is driving the real desktop. No concurrent activity may mask it.
    expect(resolveAgentState({
      computerUseActive: true,
      generating: true,
      speaking: true,
      blocked: true,
      researchActive: true,
      pendingApprovals: 5,
      mode: 'locked',
    })).toBe('computeruse');
  });

  it('surfaces a refusal above ordinary activity', () => {
    expect(resolveAgentState({ blocked: true, generating: true, researchActive: true }))
      .toBe('blocked');
  });

  it('does not let Locked mode hide a session that is already running', () => {
    // Entering Locked mode stops new tool requests; it does not stop a session
    // that is mid-flight, so the indicator must keep showing the live one.
    expect(resolveAgentState({ researchActive: true, mode: 'locked' })).toBe('researching');
    expect(resolveAgentState({ computerUseActive: true, mode: 'locked' })).toBe('computeruse');
  });

  it('distinguishes one pending approval from a batch', () => {
    expect(resolveAgentState({ pendingApprovals: 0 })).toBe('idle');
    expect(resolveAgentState({ pendingApprovals: 1 })).toBe('pending');
    expect(resolveAgentState({ pendingApprovals: 2 })).toBe('batch');
  });

  it('reports locked only when genuinely idle', () => {
    expect(resolveAgentState({ mode: 'locked' })).toBe('locked');
    expect(resolveAgentState({ mode: 'assist' })).toBe('idle');
  });

  it('prefers speaking over thinking once tokens arrive', () => {
    expect(resolveAgentState({ generating: true })).toBe('thinking');
    expect(resolveAgentState({ generating: true, speaking: true })).toBe('speaking');
  });

  it('shows browser activity above the enclosing research session', () => {
    expect(resolveAgentState({ researchActive: true, browserActive: true })).toBe('browser');
  });
});
