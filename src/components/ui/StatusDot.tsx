import type { AgentTone } from '@/types';
import { toneVar } from '@/lib/utils';

interface StatusDotProps {
  tone: AgentTone;
  pulse?: boolean;
}

export function StatusDot({ tone, pulse = false }: StatusDotProps) {
  const color = toneVar(tone);
  return (
    <span
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        boxShadow: pulse ? `0 0 0 0 ${color}` : undefined,
        animation: pulse ? 'none' : undefined,
        opacity: tone === 'grey' ? 0.6 : 1,
      }}
      aria-hidden="true"
    />
  );
}
