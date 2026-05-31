import { ESCALATIONS } from '@/data/mock';
import { Pill } from '@/components/ui/Pill';
import { Icon } from '@/components/ui/Icon';
import type { AgentTone } from '@/types';

const STATUS_TONE: Record<string, AgentTone> = {
  ready: 'green', queued: 'amber', 'in-progress': 'live',
};

export function EscalationPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>
      <div className="panel">
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line-soft)' }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Escalation Queue</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 2 }}>
            Tasks too complex for the local model — escalate to Claude Code or OpenCode
          </div>
        </div>
        {ESCALATIONS.map((es) => (
          <div key={es.id} style={{ padding: '14px var(--s5)', borderBottom: '1px solid var(--line-soft)', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--s3)' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--txt-0)' }}>{es.task}</div>
                <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 3 }}>{es.reason}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 4 }}>{es.repo}</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                <Pill tone={STATUS_TONE[es.status] ?? 'grey'}>{es.status}</Pill>
                <span style={{ fontSize: 11, color: 'var(--txt-2)' }}>{es.agent}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--s2)' }}>
              <button className="btn btn-sm">
                <Icon name="layers" size={13} />Copy handoff
              </button>
              <button className="btn btn-sm btn-primary">
                <Icon name="arrow-up" size={13} />Open in {es.agent}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
