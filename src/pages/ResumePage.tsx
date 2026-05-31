import { EmptyState } from '@/components/ui/EmptyState';

export function ResumePage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <EmptyState
        icon="doc"
        title="Resume Pipeline"
        desc="Project evidence rows, achievement bullets, and skills extracted from completed work — ready for resume and application drafting."
      />
    </div>
  );
}
