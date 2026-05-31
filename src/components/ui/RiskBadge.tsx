import type { RiskLevel, AgentTone } from '@/types';
import { toneVar, toneBg } from '@/lib/utils';

interface RiskBadgeProps {
  level: RiskLevel;
  compact?: boolean;
}

const RISK_TONE: Record<RiskLevel, AgentTone> = {
  low:      'green',
  medium:   'amber',
  high:     'red',
  disabled: 'grey',
};

export function RiskBadge({ level, compact = false }: RiskBadgeProps) {
  const tone = RISK_TONE[level];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: compact ? '1px 6px' : '2px 8px',
        borderRadius: 'var(--r-pill)',
        fontSize: 10.5,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        background: toneBg(tone),
        color: toneVar(tone),
        whiteSpace: 'nowrap',
      }}
    >
      {level}
    </span>
  );
}
