import { EmptyState } from '@/components/ui/EmptyState';

const CANDIDATES = [
  { title: 'MAT292 PS6 due',    date: 'Mon Jun 2 · 23:59', source: 'Quercus email',     conf: 'High'   },
  { title: 'ESC203 team sync',  date: 'Tue Jun 3 · 14:00', source: 'Calendar invite',   conf: 'High'   },
  { title: 'HtN submission',    date: 'Fri Jun 6 · 18:00',  source: 'Devpost reminder',  conf: 'Medium' },
];

export function CalendarPage() {
  return (
    <div style={{ maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>
      <div className="panel">
        <div style={{ padding: 'var(--s4) var(--s5)', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Calendar Candidates</div>
            <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 2 }}>Review before export to Google Calendar</div>
          </div>
          <button className="btn btn-sm btn-primary">Export approved as .ics</button>
        </div>
        {CANDIDATES.map((c, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--s4)', padding: '12px var(--s5)', borderBottom: '1px solid var(--line-soft)' }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{c.title}</div>
              <div style={{ fontSize: 11.5, color: 'var(--txt-2)', marginTop: 2 }}>{c.source}</div>
            </div>
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--txt-1)' }}>{c.date}</div>
            <span style={{ fontSize: 11, fontWeight: 600, color: c.conf === 'High' ? 'var(--green)' : 'var(--amber)' }}>{c.conf}</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12 }}>
              <input type="checkbox" defaultChecked={c.conf === 'High'} style={{ accentColor: 'var(--live)' }} />
              Approve
            </label>
          </div>
        ))}
        {CANDIDATES.length === 0 && <EmptyState icon="cal" title="No calendar candidates" desc="Extracted calendar candidates will appear here for review before export." />}
      </div>
    </div>
  );
}
