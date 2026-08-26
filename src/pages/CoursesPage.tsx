/**
 * Courses — PRD §22.
 *
 * §22 asks for syllabus/lecture/assignment/past-exam intake, Quercus/Canvas
 * reads, weak-concept tracking and study planning. Uploads route through the
 * Raw Inbox (the one place with classification and approval), and Canvas
 * assignments are pulled per course when a token is configured.
 *
 * The AI learning safeguard is a real constraint, not decoration: Canvas access
 * is GET-only and assignment SUBMISSION has no code path in the backend at all.
 */
import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultCourse, QuercusAssignment, QuercusCourse } from '@/lib/api';
import { EntityListPage } from '@/components/entities/EntityListPage';
import type { EntityAction } from '@/components/entities/EntityCard';
import { Icon } from '@/components/ui/Icon';

export function CoursesPage() {
  const navigate = useAppStore((s) => s.navigate);
  const showToast = useAppStore((s) => s.showToast);

  const [quercusReady, setQuercusReady] = useState(false);
  const [canvasCourses, setCanvasCourses] = useState<QuercusCourse[]>([]);
  const [assignments, setAssignments] = useState<Record<string, QuercusAssignment[]>>({});

  const load = useCallback(async () => (await api.getVaultCourses()).courses, []);

  useEffect(() => {
    api.quercusStatus()
      .then((s) => {
        setQuercusReady(s.configured);
        if (s.configured) {
          api.quercusCourses(50)
            .then((r) => setCanvasCourses(r.courses))
            .catch(() => setCanvasCourses([]));
        }
      })
      .catch(() => setQuercusReady(false));
  }, []);

  /** Match a vault course note to a Canvas course by code, then by name. */
  const matchCanvas = useCallback((course: VaultCourse): QuercusCourse | undefined => {
    const key = course.name.toLowerCase();
    return canvasCourses.find((c) => c.courseCode && key.includes(c.courseCode.toLowerCase()))
        ?? canvasCourses.find((c) => c.name && c.name.toLowerCase().includes(key));
  }, [canvasCourses]);

  const loadAssignments = useCallback(async (course: VaultCourse) => {
    const canvas = matchCanvas(course);
    if (!canvas) {
      showToast(`No Canvas course matches "${course.name}".`);
      return;
    }
    try {
      const res = await api.quercusAssignments(canvas.courseId, 8);
      setAssignments((a) => ({ ...a, [course.id]: res.assignments }));
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not read assignments.');
    }
  }, [matchCanvas, showToast]);

  const actionsFor = useCallback((course: VaultCourse): EntityAction[] => {
    const actions: EntityAction[] = [
      { label: 'Upload syllabus', title: 'Route a syllabus through the Raw Inbox', onClick: () => navigate('inbox') },
      { label: 'Upload lecture', title: 'Route lecture notes through the Raw Inbox', onClick: () => navigate('inbox') },
      { label: 'Upload assignment', title: 'Route an assignment through the Raw Inbox', onClick: () => navigate('inbox') },
      { label: 'Quercus email', title: 'Import Canvas notifications', onClick: () => navigate('email') },
      { label: 'Study plan', title: 'Schedule study blocks as calendar candidates', onClick: () => navigate('calendar') },
    ];
    if (quercusReady && matchCanvas(course)) {
      actions.unshift({
        label: 'Assignments',
        title: 'Read upcoming Canvas assignments (read-only)',
        onClick: () => loadAssignments(course),
      });
    }
    return actions;
  }, [navigate, quercusReady, matchCanvas, loadAssignments]);

  return (
    <EntityListPage<VaultCourse>
      title="Courses"
      kind="course"
      pathHint="wiki/courses/ · raw/courses/"
      icon="book"
      newLabel="New Course"
      emptyTitle="No courses found"
      emptyDesc="No .md files in wiki/courses/ and no folders in raw/courses/. Create a course or route course files from the Raw Inbox."
      safetyNote={
        <>
          Canvas/Quercus access is <strong>read-only</strong>: GET requests only, host pinned,
          redirects disabled. Assignment submission has no code path and never will. AI help here
          is for concepts, hints, similar examples and practice — not for producing graded work you
          have not attempted.
        </>
      }
      load={load}
      actionsFor={actionsFor}
      create={{
        note: 'Creates the course using `brain new-course <code>`.',
        fields: [
          { key: 'code', label: 'Course code', placeholder: 'ESC203', required: true },
          { key: 'name', label: 'Course title', placeholder: 'Optional course title' },
        ],
        submit: (values) => api.createCourse({
          code: values.code.trim(),
          name: values.name?.trim() || undefined,
        }),
      }}
      renderExtra={(course) => {
        const rows = assignments[course.id];
        if (!rows) return null;
        return (
          <div className="panel panel-pad" style={{ padding: 'var(--s3)' }}>
            <div className="eyebrow" style={{ marginBottom: 4 }}>
              Canvas assignments · untrusted content
            </div>
            {rows.length === 0 ? (
              <div style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>Nothing upcoming.</div>
            ) : rows.map((a) => (
              <div key={a.assignmentId} style={{ display: 'flex', gap: 6, fontSize: 10.5, color: 'var(--txt-2)' }}>
                <span className="mono" style={{ color: 'var(--txt-3)', flexShrink: 0, minWidth: 74 }}>
                  {a.dueAt ? a.dueAt.slice(0, 10) : 'no due date'}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.name}
                </span>
                {a.htmlUrl && (
                  <a href={a.htmlUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--live)' }}>open</a>
                )}
              </div>
            ))}
            <div style={{ fontSize: 9.5, color: 'var(--txt-3)', marginTop: 5, display: 'flex', gap: 4, alignItems: 'center' }}>
              <Icon name="shield" size={10} />
              Read-only. Submitting from this app is not possible.
            </div>
          </div>
        );
      }}
    />
  );
}
