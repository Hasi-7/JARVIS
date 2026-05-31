const DOMAIN_COLOR: Record<string, { color: string; bg: string }> = {
  course:    { color: 'var(--live)',   bg: 'var(--live-bg)' },
  project:   { color: 'var(--violet)', bg: 'var(--violet-bg)' },
  hackathon: { color: 'var(--amber)',  bg: 'var(--amber-bg)' },
  business:  { color: 'var(--green)',  bg: 'var(--green-bg)' },
  research:  { color: 'var(--live)',   bg: 'var(--live-bg)' },
  ops:       { color: 'var(--grey)',   bg: 'oklch(0.62 0.006 var(--base-h) / 0.15)' },
  personal:  { color: 'var(--grey)',   bg: 'oklch(0.62 0.006 var(--base-h) / 0.15)' },
};

interface TagChipProps {
  domain: string;
}

export function TagChip({ domain }: TagChipProps) {
  const { color, bg } = DOMAIN_COLOR[domain] ?? DOMAIN_COLOR.ops;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1px 7px',
        borderRadius: 'var(--r-pill)',
        fontSize: 10.5,
        fontWeight: 600,
        color,
        background: bg,
        whiteSpace: 'nowrap',
      }}
    >
      {domain}
    </span>
  );
}
