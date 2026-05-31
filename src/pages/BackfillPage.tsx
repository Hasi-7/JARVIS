import { EmptyState } from '@/components/ui/EmptyState';

export function BackfillPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="layers"
        title="Backfill"
        desc="Old repos and projects waiting to be catalogued, closed out, and archived into the vault. Current: 11 / 32 complete (34%)."
      />
    </div>
  );
}
