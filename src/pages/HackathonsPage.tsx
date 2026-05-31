import { EmptyState } from '@/components/ui/EmptyState';

export function HackathonsPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="flag"
        title="Hackathons"
        desc="Hackathon submissions, team notes, devpost exports, and post-mortems — all organized and synced from the vault."
      />
    </div>
  );
}
