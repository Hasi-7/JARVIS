import type { AgentTone } from '@/types';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { toneVar, toneBg } from '@/lib/utils';

interface StatusCardProps {
  label: string;
  value: number | string;
  sub: string;
  tone?: AgentTone;
  icon?: string;
  accent?: boolean;
  onClick?: () => void;
}

export function StatusCard({ label, value, sub, tone, icon, accent, onClick }: StatusCardProps) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        padding: 'var(--s4)',
        background: accent && tone ? toneBg(tone) : 'var(--surface)',
        border: `1px solid ${accent && tone ? toneVar(tone) + '55' : 'var(--line-soft)'}`,
        borderRadius: 'var(--r3)',
        cursor: onClick ? 'pointer' : 'default',
        textAlign: 'left',
        transition: 'background var(--fast) var(--ease), border-color var(--fast) var(--ease)',
        width: '100%',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-2)'; }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background =
          accent && tone ? toneBg(tone) : 'var(--surface)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {tone && <StatusDot tone={tone} />}
        {icon && !tone && (
          <span style={{ color: 'var(--txt-2)', display: 'flex' }}>
            <Icon name={icon} size={13} />
          </span>
        )}
        <span className="eyebrow" style={{ fontSize: 10 }}>{label}</span>
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: '-0.01em',
          color: tone ? toneVar(tone) : 'var(--txt-0)',
          fontFamily: 'var(--font-mono)',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--txt-2)' }}>{sub}</div>
    </button>
  );
}
