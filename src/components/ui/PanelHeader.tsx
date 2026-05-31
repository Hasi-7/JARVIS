import { Icon } from './Icon';

interface PanelHeaderProps {
  icon?: string;
  title: string;
  sub?: string;
  right?: React.ReactNode;
}

export function PanelHeader({ icon, title, sub, right }: PanelHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--s2)',
        marginBottom: 'var(--s4)',
      }}
    >
      {icon && (
        <span style={{ color: 'var(--txt-2)', display: 'flex', flexShrink: 0 }}>
          <Icon name={icon} size={15} />
        </span>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--txt-0)' }}>{title}</span>
        {sub && (
          <span style={{ fontSize: 11, color: 'var(--txt-2)', marginLeft: 8 }}>{sub}</span>
        )}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}
