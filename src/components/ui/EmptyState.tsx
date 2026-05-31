import { Icon } from './Icon';

interface EmptyStateProps {
  icon: string;
  title: string;
  desc: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, desc, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--s3)',
        padding: 'var(--s8)',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 'var(--r3)',
          background: 'var(--surface-2)',
          border: '1px solid var(--line)',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--txt-2)',
        }}
      >
        <Icon name={icon} size={22} />
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--txt-0)' }}>{title}</div>
        <div style={{ fontSize: 12.5, color: 'var(--txt-2)', marginTop: 4, maxWidth: 320 }}>{desc}</div>
      </div>
      {action && <div style={{ marginTop: 4 }}>{action}</div>}
    </div>
  );
}
