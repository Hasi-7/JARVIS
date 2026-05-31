import type { ConfLevel } from '@/types';

interface ConfidenceBadgeProps {
  level: ConfLevel;
}

const BAR_COUNT: Record<ConfLevel, number> = {
  Low: 1, Medium: 2, High: 3,
};

const BAR_COLOR: Record<ConfLevel, string> = {
  Low: 'var(--red)', Medium: 'var(--amber)', High: 'var(--green)',
};

export function ConfidenceBadge({ level }: ConfidenceBadgeProps) {
  const bars = BAR_COUNT[level];
  const color = BAR_COLOR[level];
  return (
    <span
      title={`Confidence: ${level}`}
      style={{
        display: 'inline-flex',
        alignItems: 'flex-end',
        gap: 2,
        height: 14,
      }}
    >
      {[1, 2, 3].map((n) => (
        <span
          key={n}
          style={{
            width: 3,
            height: n === 1 ? 5 : n === 2 ? 9 : 13,
            borderRadius: 2,
            background: n <= bars ? color : 'var(--line-strong)',
          }}
        />
      ))}
    </span>
  );
}
