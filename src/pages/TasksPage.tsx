import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { useAppStore } from '@/store/useAppStore';

export function TasksPage() {
  const navigate = useAppStore((s) => s.navigate);
  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <EmptyState
        icon="check"
        title="Tasks"
        desc="Action items extracted from standup notes, conversations, and agent proposals will appear here, synced to the vault."
        action={
          <button className="btn" onClick={() => navigate('agent')}>
            <Icon name="spark" size={14} />Ask agent to extract tasks
          </button>
        }
      />
    </div>
  );
}
