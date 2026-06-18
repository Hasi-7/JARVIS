import type { SystemService } from '@/types';
import { StatusDot } from '@/components/ui/StatusDot';
import { STATE_TO_TONE } from '@/lib/utils';
import { toneVar } from '@/lib/utils';

interface SystemRowProps {
  service: SystemService;
}

export function SystemRow({ service }: SystemRowProps) {
  const tone = STATE_TO_TONE[service.state];
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--s3)',
        padding: '8px 0',
        borderBottom: '1px solid var(--line-soft)',
      }}
    >
      <StatusDot tone={tone} pulse={service.state === 'ready' || service.state === 'idle'} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--txt-0)' }}>{service.label}</div>
        <div
          className="mono"
          style={{
            fontSize: 10.5,
            color: 'var(--txt-2)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {service.detail}
        </div>
      </div>
      <span
        style={{
          fontSize: 10.5,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: toneVar(tone),
          whiteSpace: 'nowrap',
        }}
      >
        {service.statusLabel ?? service.state}
      </span>
    </div>
  );
}
