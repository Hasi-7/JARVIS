import type { Approval } from '@/types';
import { ConfidenceBadge } from '@/components/ui/ConfidenceBadge';
import { RiskBadge } from '@/components/ui/RiskBadge';

interface ApprovalRowProps {
  approval: Approval;
}

export function ApprovalRow({ approval }: ApprovalRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--s3)',
        padding: '10px 0',
        borderBottom: '1px solid var(--line-soft)',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 12.5,
            fontWeight: 500,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            color: 'var(--txt-0)',
          }}
        >
          {approval.title}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--txt-2)',
            marginTop: 2,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {approval.reason}
        </div>
      </div>
      <ConfidenceBadge level={approval.conf} />
      <RiskBadge level={approval.risk} compact />
    </div>
  );
}
