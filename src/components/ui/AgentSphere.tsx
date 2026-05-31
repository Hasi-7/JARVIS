import type { AgentStateKey, SphereVariant, AgentTone } from '@/types';
import { toneVar } from '@/lib/utils';
import { AGENT_STATES } from '@/data/mock';

interface AgentSphereProps {
  state?: AgentStateKey;
  size?: number;
  variant?: SphereVariant;
  count?: number;
}

const TONE_MAP: Record<AgentTone, string> = {
  live:   'var(--live)',
  amber:  'var(--amber)',
  red:    'var(--red)',
  violet: 'var(--violet)',
  green:  'var(--green)',
  grey:   'var(--grey)',
};

interface RingProps {
  r: number;
  w?: number;
  dash?: string;
  op?: number;
  cls?: string;
  color?: string;
}

function Ring({ r, w = 1, dash, op = 1, cls, color }: RingProps & { c?: string }) {
  return (
    <circle
      className={cls}
      cx={50}
      cy={50}
      r={r}
      fill="none"
      stroke={color ?? 'currentColor'}
      strokeWidth={w}
      strokeOpacity={op}
      strokeDasharray={dash}
      strokeLinecap="round"
    />
  );
}

export function AgentSphere({
  state = 'idle',
  size = 180,
  variant = 'orb',
  count,
}: AgentSphereProps) {
  const meta = AGENT_STATES[state];
  const tone: AgentTone = meta?.tone ?? 'live';
  const c = TONE_MAP[tone] ?? TONE_MAP.live;
  const animated = !['locked', 'blocked'].includes(state);
  const breathe  = ['idle', 'listening', 'speaking', 'guarded'].includes(state);

  const coreOpacity =
    variant === 'rings'   ? 0.10 :
    variant === 'minimal' ? 0.16 : 0.24;

  const coreShadow =
    variant === 'minimal'
      ? `0 0 ${size * 0.10}px -2px ${c}`
      : `0 0 ${size * 0.20}px -4px ${c}, inset 0 0 ${size * 0.18}px ${c}`;

  const layers: React.ReactNode[] = [];

  if (variant !== 'minimal' && state !== 'blocked') {
    layers.push(
      <g key="base">
        <Ring r={46} w={0.8} op={0.22} color={c} />
        {variant === 'rings' && <Ring r={38} w={0.6} op={0.16} color={c} />}
      </g>
    );
  }

  if (state === 'idle') {
    layers.push(
      <g key="idle" className={animated ? 'sph-rot' : ''}>
        <Ring r={42} w={0.8} dash="1 7" op={0.4} color={c} />
      </g>
    );
  }

  if (state === 'listening') {
    layers.push(
      <g key="listening">
        <Ring r={40} w={1.4} op={0.9} cls={animated ? 'sph-pulse' : ''} color={c} />
        <Ring r={46} w={0.8} op={0.5} color={c} />
      </g>
    );
  }

  if (state === 'thinking') {
    layers.push(
      <g key="thinking">
        <g className={animated ? 'sph-rot-fast' : ''}>
          <Ring r={34} w={2} dash="34 80" op={0.95} color={c} />
        </g>
        <g className={animated ? 'sph-rot-rev' : ''}>
          <Ring r={42} w={1} dash="2 10" op={0.5} color={c} />
        </g>
      </g>
    );
  }

  if (state === 'speaking') {
    layers.push(
      <g key="speaking">
        <Ring r={40} w={1.2} op={0.8} cls={animated ? 'sph-pulse' : ''} color={c} />
      </g>
    );
    layers.push(
      <g key="bars">
        {[0, 1, 2, 3, 4].map((i) => (
          <rect
            key={i}
            x={42 + i * 3.4}
            y={44}
            width={1.8}
            height={12}
            rx={0.9}
            fill={c}
            style={{
              transformOrigin: '50% 50%',
              animation: animated ? `sph-wave ${0.7 + i * 0.12}s ease-in-out infinite` : 'none',
              animationDelay: `${i * 0.08}s`,
            }}
          />
        ))}
      </g>
    );
  }

  if (state === 'researching' || state === 'browser') {
    layers.push(
      <g key="research">
        <Ring r={40} w={0.8} dash="2 6" op={0.4} color={c} />
        <g className={animated ? 'sph-orbit' : ''}>
          <circle cx={50} cy={8} r={3} fill={c} />
        </g>
        {state === 'browser' && <Ring r={30} w={0.8} op={0.4} color={c} />}
        {state === 'browser' && (
          <ellipse cx={50} cy={50} rx={30} ry={12} fill="none" stroke={c} strokeWidth={0.8} strokeOpacity={0.4} />
        )}
      </g>
    );
  }

  if (state === 'computeruse') {
    layers.push(
      <g key="computeruse">
        <g className={animated ? 'sph-rot' : ''}>
          <Ring r={40} w={2.4} dash="20 60" op={0.9} color={c} />
        </g>
        <path d="M47 44 L47 58 L51 54 L54 59 L56 58 L53 53 L58 53 Z" fill={c} opacity={0.95} />
      </g>
    );
  }

  if (state === 'pending') {
    layers.push(
      <g key="pending" className={animated ? 'sph-flash' : ''}>
        <Ring r={42} w={2.2} op={1} color={c} />
      </g>
    );
  }

  if (state === 'batch' || state === 'escalation') {
    layers.push(
      <g key="batch" className={animated ? 'sph-rot' : ''}>
        <Ring r={42} w={2.6} dash="10 7" op={0.95} color={c} />
      </g>
    );
  }

  if (state === 'blocked') {
    layers.push(
      <g key="blocked">
        <Ring r={34} w={2.4} op={1} color={c} />
        <path d="M40 40 L60 60" stroke={c} strokeWidth={2.4} strokeLinecap="round" />
      </g>
    );
  }

  if (state === 'guarded') {
    layers.push(
      <g key="guarded">
        <Ring r={42} w={1.4} op={0.7} color={c} />
        <path
          d="M50 33 L62 38 V49 c0 8-5 13-12 15 -7-2-12-7-12-15 V38 Z"
          fill="none"
          stroke={c}
          strokeWidth={2}
          strokeLinejoin="round"
          opacity={0.95}
        />
        <path d="M45 49 l4 4 7-8" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </g>
    );
  }

  if (state === 'locked') {
    layers.push(
      <g key="locked">
        <Ring r={40} w={1} op={0.5} color={toneVar('grey')} />
      </g>
    );
  }

  return (
    <div className="sph-wrap" style={{ width: size, height: size }}>
      {/* core orb */}
      <div
        style={{
          width: size * 0.56,
          height: size * 0.56,
          borderRadius: '50%',
          background: `radial-gradient(circle at 38% 32%, ${c}, transparent 72%)`,
          opacity: coreOpacity,
          boxShadow: coreShadow,
          animation: breathe && animated ? 'sph-breathe 5.5s ease-in-out infinite' : 'none',
          filter: state === 'locked' ? 'grayscale(1)' : 'none',
        }}
      />
      {/* presence dot */}
      <div
        style={{
          position: 'absolute',
          width: size * 0.13,
          height: size * 0.13,
          borderRadius: '50%',
          background: c,
          opacity: state === 'locked' ? 0.4 : 0.92,
          boxShadow: `0 0 ${size * 0.08}px ${c}`,
          animation: breathe && animated ? 'sph-breathe 5.5s ease-in-out infinite' : 'none',
        }}
      />
      {/* SVG ring layer */}
      <svg className="sph-svg" viewBox="0 0 100 100">
        {layers}
      </svg>
      {/* count badge */}
      {count != null && (state === 'batch' || state === 'escalation') && (
        <div
          style={{
            position: 'absolute',
            right: size * 0.06,
            top: size * 0.06,
            minWidth: 22,
            height: 22,
            padding: '0 6px',
            borderRadius: 11,
            background: c,
            color: 'var(--bg-0)',
            fontWeight: 700,
            fontSize: 12,
            display: 'grid',
            placeItems: 'center',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {count}
        </div>
      )}
    </div>
  );
}
