import type { AiSource } from '@/types';

interface SourceGlyphProps {
  source: AiSource;
}

const SOURCE_META: Record<AiSource, { label: string; color: string; bg: string; abbr: string }> = {
  claude:   { label: 'Claude',   color: 'oklch(0.72 0.13 290)', bg: 'oklch(0.72 0.13 290 / 0.14)', abbr: 'C' },
  chatgpt:  { label: 'ChatGPT',  color: 'oklch(0.74 0.14 160)', bg: 'oklch(0.74 0.14 160 / 0.13)', abbr: 'G' },
  opencode: { label: 'OpenCode', color: 'oklch(0.70 0.10 220)', bg: 'oklch(0.70 0.10 220 / 0.13)', abbr: 'O' },
};

export function SourceGlyph({ source }: SourceGlyphProps) {
  const meta = SOURCE_META[source];
  return (
    <span
      title={meta.label}
      style={{
        display: 'inline-grid',
        placeItems: 'center',
        width: 26,
        height: 26,
        borderRadius: 'var(--r2)',
        background: meta.bg,
        color: meta.color,
        fontSize: 11,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        flexShrink: 0,
      }}
    >
      {meta.abbr}
    </span>
  );
}
