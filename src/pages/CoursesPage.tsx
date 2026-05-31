import { EmptyState } from '@/components/ui/EmptyState';

export function CoursesPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="book"
        title="Courses"
        desc="Course notes, lecture PDFs, assignment deadlines, and Quercus data — classified and routed from the inbox into vault folders per course."
      />
    </div>
  );
}
