import type { TodayBlock } from '@/types';
import { Icon } from '@/components/ui/Icon';
import { TagChip } from '@/components/ui/TagChip';
import { Pill } from '@/components/ui/Pill';

interface PlanBlockProps {
  block: TodayBlock;
}

export function PlanBlock({ block }: PlanBlockProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '54px 1fr auto',
        alignItems: 'center',
        gap: 'var(--s3)',
        padding: '9px 12px',
        borderRadius: 'var(--r2)',
        background: block.now ? 'var(--live-bg)' : 'transparent',
        border: `1px solid ${block.now ? 'var(--live-line)' : 'transparent'}`,
        opacity: block.done ? 0.55 : 1,
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 12,
          color: block.now ? 'var(--live)' : 'var(--txt-2)',
          fontWeight: 600,
        }}
      >
        {block.time}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            textDecoration: block.done ? 'line-through' : 'none',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            color: 'var(--txt-0)',
          }}
        >
          {block.title}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 3 }}>
          <TagChip domain={block.tag} />
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
            {block.dur}
          </span>
          {block.now && <Pill tone="live">In progress</Pill>}
        </div>
      </div>
      {block.done ? (
        <span style={{ color: 'var(--green)', display: 'flex' }}>
          <Icon name="check" size={15} />
        </span>
      ) : (
        <span
          style={{
            display: 'inline-block',
            width: 15,
            height: 15,
            borderRadius: '50%',
            border: '1.5px solid var(--line-strong)',
            flexShrink: 0,
          }}
        />
      )}
    </div>
  );
}
