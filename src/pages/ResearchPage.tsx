import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';

const TIME_BUDGETS = ['5 min', '10 min', '15 min', '20 min', '30 min', '60 min'];
const DEPTH_OPTIONS = ['Quick summary', 'Decision brief', 'Deep dive'];

export function ResearchPage() {
  return (
    <div style={{ maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* query builder */}
      <div className="panel panel-pad">
        <div className="eyebrow" style={{ marginBottom: 'var(--s4)' }}>New research run</div>
        <textarea
          placeholder="What should the agent research? e.g. 'Current NemoClaw / OpenShell policy format'"
          rows={3}
          style={{
            width: '100%',
            background: 'var(--surface-2)',
            border: '1px solid var(--line)',
            borderRadius: 'var(--r2)',
            padding: '10px 12px',
            fontSize: 13,
            color: 'var(--txt-0)',
            fontFamily: 'var(--font-ui)',
            resize: 'vertical',
            outline: 'none',
            marginBottom: 'var(--s4)',
          }}
        />
        <div style={{ display: 'flex', gap: 'var(--s5)', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 'var(--s2)' }}>Time budget</div>
            <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap' }}>
              {TIME_BUDGETS.map((t, i) => (
                <button key={t} className={`btn btn-sm${i === 1 ? ' btn-primary' : ''}`}>{t}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="eyebrow" style={{ marginBottom: 'var(--s2)' }}>Depth</div>
            <div style={{ display: 'flex', gap: 'var(--s2)' }}>
              {DEPTH_OPTIONS.map((d, i) => (
                <button key={d} className={`btn btn-sm${i === 1 ? ' btn-primary' : ''}`}>{d}</button>
              ))}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 'var(--s4)', display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary">
            <Icon name="search" size={14} />
            Start research
          </button>
        </div>
      </div>

      {/* empty state — no active run */}
      <EmptyState
        icon="search"
        title="No active research run"
        desc="Configure a query above and start a time-boxed research run. Results arrive with source citations, confidence level, and a save-to-vault proposal."
      />
    </div>
  );
}
