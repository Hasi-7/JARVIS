import { EmptyState } from '@/components/ui/EmptyState';

export function ProjectsPage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="cube"
        title="Projects"
        desc="Active and archived projects from the vault will be listed here. Each project links to its raw files, escalations, research packets, and open tasks."
      />
    </div>
  );
}
