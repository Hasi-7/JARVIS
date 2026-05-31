import { clsx, type ClassValue } from 'clsx';
import type { AgentTone, SystemState } from '@/types';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function toneVar(tone: AgentTone): string {
  const map: Record<AgentTone, string> = {
    live:   'var(--live)',
    amber:  'var(--amber)',
    red:    'var(--red)',
    violet: 'var(--violet)',
    green:  'var(--green)',
    grey:   'var(--grey)',
  };
  return map[tone];
}

export function toneBg(tone: AgentTone): string {
  const map: Record<AgentTone, string> = {
    live:   'var(--live-bg)',
    amber:  'var(--amber-bg)',
    red:    'var(--red-bg)',
    violet: 'var(--violet-bg)',
    green:  'var(--green-bg)',
    grey:   'oklch(0.62 0.006 var(--base-h) / 0.15)',
  };
  return map[tone];
}

export function toneLine(tone: AgentTone): string {
  const map: Record<AgentTone, string> = {
    live:   'var(--live-line)',
    amber:  'var(--amber-line)',
    red:    'var(--red-line)',
    violet: 'var(--violet-line)',
    green:  'var(--green-line)',
    grey:   'oklch(0.62 0.006 var(--base-h) / 0.30)',
  };
  return map[tone];
}

export const STATE_TO_TONE: Record<SystemState, AgentTone> = {
  ready:    'green',
  idle:     'live',
  partial:  'amber',
  disabled: 'grey',
  blocked:  'red',
};
