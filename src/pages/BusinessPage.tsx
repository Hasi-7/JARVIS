import { EmptyState } from '@/components/ui/EmptyState';

export function BusinessPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="chart"
        title="Business"
        desc="Customer discovery notes, finance documents, and business decision logs — organized by entity (e.g. Tutoring SaaS) and routed from inbox."
      />
    </div>
  );
}
