import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultCourse } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function truncate(text: string | null, n = 180): string {
  if (!text) return '';
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text;
}

function CourseCard({ course, vaultPath }: { course: VaultCourse; vaultPath: string | null }) {
  const obsidianUrl =
    vaultPath && course.wikiPath
      ? createObsidianOpenUrl(vaultPath, course.wikiPath)
      : null;

  return (
    <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', minHeight: 120 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--txt-0)', lineHeight: 1.3 }}>
        {course.name}
      </div>

      {course.wikiPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="doc" size={11} style={{ color: 'var(--live)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--live)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={course.wikiPath}>
            {course.wikiPath}
          </span>
        </div>
      )}
      {course.rawPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="folder" size={11} style={{ color: 'var(--violet)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--violet)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={course.rawPath}>
            {course.rawPath}
          </span>
        </div>
      )}

      {course.preview && (
        <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5, flex: 1 }}>
          {truncate(course.preview)}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 'var(--s2)' }}>
        <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>{fmtDate(course.lastModified)}</span>

        {obsidianUrl ? (
          <a
            href={obsidianUrl}
            className="btn btn-sm btn-ghost"
            style={{ fontSize: 10.5, padding: '2px 7px', textDecoration: 'none' }}
            title="Open this note in Obsidian"
          >
            Open note
          </a>
        ) : course.rawPath && !course.wikiPath ? (
          <button className="btn btn-sm btn-ghost" disabled style={{ fontSize: 10.5, padding: '2px 7px', opacity: 0.35 }} title="No wiki note — raw folder only">
            Raw folder
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function CoursesPage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const [courses,  setCourses]  = useState<VaultCourse[] | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultCourses();
      setCourses(res.courses);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load courses.');
      setCourses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const vaultPath = backendConfig?.vaultPath ?? null;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Courses</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/courses/ · raw/courses/ — {vaultPath ?? '—'}
          </div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Refresh
        </button>
      </div>

      {/* error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* loading */}
      {loading && courses === null && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {/* empty */}
      {!loading && courses !== null && courses.length === 0 && (
        <EmptyState
          icon="book"
          title="No courses found"
          desc="No .md files in wiki/courses/ and no folders in raw/courses/. Route course files from the Raw Inbox to populate this page."
        />
      )}

      {/* cards */}
      {courses !== null && courses.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {courses.map((c) => <CourseCard key={c.id} course={c} vaultPath={vaultPath} />)}
        </div>
      )}

      {courses !== null && courses.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          {courses.length} course{courses.length === 1 ? '' : 's'} found
        </div>
      )}

      {/* footer */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        Read-only. No vault files are modified. "Open note" links open Obsidian — no writes occur.
      </div>

    </div>
  );
}
