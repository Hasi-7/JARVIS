import { CONSOLIDATED } from '@/data/mock';
import { SourceGlyph } from '@/components/ui/SourceGlyph';
import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';

export function ConsolidatePage() {
  return (
    <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>
      <div className="panel">
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>AI Consolidation</div>
            <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 2 }}>Capture useful work from ChatGPT, Claude, and OpenCode into the Obsidian vault</div>
          </div>
          <button className="btn btn-primary">
            <Icon name="plus" size={14} />
            New consolidation
          </button>
        </div>
        {CONSOLIDATED.map((item) => (
          <div
            key={item.id}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--s4)', padding: '12px var(--s5)', borderBottom: '1px solid var(--line-soft)' }}
          >
            <SourceGlyph source={item.source} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--txt-0)' }}>{item.title}</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 2 }}>{item.dest}</div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--txt-2)', whiteSpace: 'nowrap' }}>{item.items}</div>
            <span style={{ fontSize: 10.5, color: 'var(--txt-3)', whiteSpace: 'nowrap' }}>{item.when}</span>
            <button className="btn btn-sm btn-ghost">Review</button>
          </div>
        ))}
        {CONSOLIDATED.length === 0 && (
          <EmptyState icon="merge" title="No consolidations yet" desc="Past AI session summaries and captures will appear here." />
        )}
      </div>
    </div>
  );
}
