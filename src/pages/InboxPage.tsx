import { EmptyState } from '@/components/ui/EmptyState';
import { useAppStore } from '@/store/useAppStore';
import { Icon } from '@/components/ui/Icon';
import { ConfidenceBadge } from '@/components/ui/ConfidenceBadge';
import { TagChip } from '@/components/ui/TagChip';

const STAGED = [
  { name: 'MAT292-L18-laplace.pdf',  size: '2.4 MB', domain: 'course',    dest: 'raw/courses/MAT292/lectures/',        conf: 'High'   as const },
  { name: 'devpost-submission.md',    size: '14 KB',  domain: 'hackathon', dest: 'raw/hackathons/Hack the North 2025/', conf: 'High'   as const },
  { name: 'customer-call-notes.txt',  size: '6 KB',   domain: 'business',  dest: 'raw/business/Tutoring SaaS/',         conf: 'Medium' as const },
  { name: 'IMG_4821.HEIC',            size: '3.1 MB', domain: 'unknown',   dest: 'raw/inbox/unclassified/',             conf: 'Low'    as const },
];

export function InboxPage() {
  const navigate = useAppStore((s) => s.navigate);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* drop zone */}
      <div
        style={{
          border: '2px dashed var(--line)',
          borderRadius: 'var(--r3)',
          padding: 'var(--s8)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 'var(--s3)',
          cursor: 'pointer',
          transition: 'border-color var(--fast) var(--ease), background var(--fast) var(--ease)',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--live-line)';
          (e.currentTarget as HTMLDivElement).style.background = 'var(--live-bg)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--line)';
          (e.currentTarget as HTMLDivElement).style.background = 'transparent';
        }}
      >
        <Icon name="upload" size={28} style={{ color: 'var(--txt-2)' }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>Drop files to stage for classification</div>
          <div style={{ fontSize: 12, color: 'var(--txt-2)', marginTop: 4 }}>
            Agent will classify domain, propose a destination, and queue for batch approval
          </div>
        </div>
        <button className="btn btn-sm">Browse files</button>
      </div>

      {/* staged files */}
      <div className="panel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line-soft)' }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Staged · {STAGED.length} files</span>
          <div style={{ display: 'flex', gap: 'var(--s2)' }}>
            <button className="btn btn-sm btn-ghost">Sync raw</button>
            <button className="btn btn-sm btn-primary">Batch approve 2 high-conf</button>
          </div>
        </div>

        {STAGED.map((f, i) => (
          <div
            key={i}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto auto auto',
              alignItems: 'center',
              gap: 'var(--s4)',
              padding: '10px var(--s5)',
              borderBottom: i < STAGED.length - 1 ? '1px solid var(--line-soft)' : 'none',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 12, color: 'var(--txt-0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {f.name}
              </div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                → {f.dest}
              </div>
            </div>
            <TagChip domain={f.domain} />
            <ConfidenceBadge level={f.conf} />
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{f.size}</span>
          </div>
        ))}
      </div>

      {STAGED.length === 0 && (
        <EmptyState
          icon="inbox"
          title="Inbox clear"
          desc="Drop files above to stage them for AI classification and routing."
          action={
            <button className="btn" onClick={() => navigate('dashboard')}>
              Back to dashboard
            </button>
          }
        />
      )}
    </div>
  );
}
