import type { AgentTone } from '@/types';
import { toneVar, toneBg, toneLine } from '@/lib/utils';

interface PillProps {
  tone: AgentTone;
  children: React.ReactNode;
}

export function Pill({ tone, children }: PillProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1px 7px',
        borderRadius: 'var(--r-pill)',
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '0.03em',
        background: toneBg(tone),
        border: `1px solid ${toneLine(tone)}`,
        color: toneVar(tone),
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}
