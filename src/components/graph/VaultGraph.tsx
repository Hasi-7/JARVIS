import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { VaultGraphResponse, GraphNode } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

/**
 * Vault graph viewer (D3d).
 *
 * Renders the Obsidian wikilink graph. Layout is a small deterministic
 * force simulation run to a fixed iteration count — no external graph library, so
 * the artifact stays self-contained and the render is reproducible.
 *
 * Read-only: it visualizes, it never edits a note or a link.
 */

interface Placed extends GraphNode {
  x: number;
  y: number;
}

const WIDTH = 900;
const HEIGHT = 560;
const ITERATIONS = 220;

/** Deterministic layout: same graph in, same picture out. */
function layout(data: VaultGraphResponse): Placed[] {
  const nodes: Placed[] = data.nodes.map((n, i) => {
    // Seed on a circle rather than at random so runs are reproducible.
    const angle = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
    const radius = Math.min(WIDTH, HEIGHT) * 0.35;
    return { ...n, x: WIDTH / 2 + Math.cos(angle) * radius, y: HEIGHT / 2 + Math.sin(angle) * radius };
  });

  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const links = data.edges
    .map((e) => [index.get(e.source), index.get(e.target)] as [number | undefined, number | undefined])
    .filter((pair): pair is [number, number] => pair[0] !== undefined && pair[1] !== undefined);

  const repulsion = 2600;
  const springLength = 90;
  const spring = 0.02;

  for (let step = 0; step < ITERATIONS; step++) {
    const damping = 1 - step / ITERATIONS;
    const fx = new Array(nodes.length).fill(0);
    const fy = new Array(nodes.length).fill(0);

    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        let dx = nodes[a].x - nodes[b].x;
        let dy = nodes[a].y - nodes[b].y;
        let distSq = dx * dx + dy * dy;
        if (distSq < 0.01) { dx = (a - b) * 0.1 + 0.1; dy = 0.1; distSq = 0.02; }
        const force = repulsion / distSq;
        const dist = Math.sqrt(distSq);
        fx[a] += (dx / dist) * force; fy[a] += (dy / dist) * force;
        fx[b] -= (dx / dist) * force; fy[b] -= (dy / dist) * force;
      }
    }

    for (const [a, b] of links) {
      const dx = nodes[b].x - nodes[a].x;
      const dy = nodes[b].y - nodes[a].y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const force = (dist - springLength) * spring;
      fx[a] += (dx / dist) * force; fy[a] += (dy / dist) * force;
      fx[b] -= (dx / dist) * force; fy[b] -= (dy / dist) * force;
    }

    for (let i = 0; i < nodes.length; i++) {
      nodes[i].x = Math.max(24, Math.min(WIDTH - 24, nodes[i].x + fx[i] * 0.08 * damping));
      nodes[i].y = Math.max(24, Math.min(HEIGHT - 24, nodes[i].y + fy[i] * 0.08 * damping));
    }
  }
  return nodes;
}

export function VaultGraph() {
  const [data, setData]       = useState<VaultGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hideOrphans, setHideOrphans] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setData(await api.vaultGraph());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the vault graph.');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => {
    if (!data) return null;
    if (!hideOrphans) return data;
    const keep = new Set(
      data.nodes.filter((n) => n.inDegree > 0 || n.outDegree > 0).map((n) => n.id),
    );
    return {
      ...data,
      nodes: data.nodes.filter((n) => keep.has(n.id)),
      edges: data.edges.filter((e) => keep.has(e.source) && keep.has(e.target)),
    };
  }, [data, hideOrphans]);

  const placed = useMemo(() => (visible ? layout(visible) : []), [visible]);
  const byId = useMemo(() => new Map(placed.map((n) => [n.id, n])), [placed]);

  const neighbours = useMemo(() => {
    if (!selected || !visible) return new Set<string>();
    const set = new Set<string>([selected]);
    for (const edge of visible.edges) {
      if (edge.source === selected) set.add(edge.target);
      if (edge.target === selected) set.add(edge.source);
    }
    return set;
  }, [selected, visible]);

  const maxDegree = useMemo(
    () => Math.max(1, ...placed.map((n) => n.inDegree + n.outDegree)),
    [placed],
  );

  return (
    <div className="panel" style={{ padding: 'var(--s4) var(--s5)', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StatusDot tone={data ? 'green' : loading ? 'amber' : 'grey'} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>Vault graph</span>
        {data && (
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>
            {data.stats.files} files → {data.stats.nodes} notes · {data.stats.edges} links ·{' '}
            {data.stats.dangling} dangling · {data.stats.orphans} orphans
          </span>
        )}
        <div style={{ flex: 1 }} />
        <button className="btn btn-sm btn-ghost" onClick={() => setHideOrphans((v) => !v)}>
          <Icon name={hideOrphans ? 'check' : 'x'} size={12} />
          Hide orphans
        </button>
        <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
          <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
          Rebuild
        </button>
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5 }}>
        Built from <strong>Obsidian wikilinks</strong> in your vault — read-only, and it
        edits no note. Hollow nodes are <strong>dangling links</strong>: referenced by a
        note but with no file of their own.
      </div>

      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2) var(--s3)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)' }}>
          {error}
        </div>
      )}

      {data && data.warnings.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-2)' }}>{data.warnings.join(' ')}</div>
      )}

      {visible && visible.nodes.length === 0 && !loading && (
        <div style={{ fontSize: 12, color: 'var(--txt-2)' }}>
          No notes with wikilinks were found in the vault.
        </div>
      )}

      {visible && visible.nodes.length > 0 && (
        <div style={{ overflowX: 'auto', border: '1px solid var(--line)', borderRadius: 'var(--r2)', background: 'var(--surface-2)' }}>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ width: '100%', minWidth: 560, display: 'block' }}>
            <g stroke="var(--line)" strokeWidth={1}>
              {visible.edges.map((edge, i) => {
                const a = byId.get(edge.source);
                const b = byId.get(edge.target);
                if (!a || !b) return null;
                const dim = selected !== null && !(neighbours.has(edge.source) && neighbours.has(edge.target));
                return (
                  <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                        opacity={dim ? 0.12 : 0.55} />
                );
              })}
            </g>
            <g>
              {placed.map((node) => {
                const degree = node.inDegree + node.outDegree;
                const radius = 4 + (degree / maxDegree) * 9;
                const dim = selected !== null && !neighbours.has(node.id);
                return (
                  <g key={node.id} opacity={dim ? 0.2 : 1}
                     style={{ cursor: 'pointer' }}
                     onClick={() => setSelected(selected === node.id ? null : node.id)}>
                    <circle
                      cx={node.x} cy={node.y} r={radius}
                      fill={node.exists ? 'var(--live)' : 'none'}
                      stroke={node.exists ? 'var(--live)' : 'var(--amber)'}
                      strokeWidth={node.exists ? 0 : 1.5}
                    />
                    {(degree > 1 || selected === node.id) && (
                      <text x={node.x} y={node.y - radius - 4} textAnchor="middle"
                            style={{ fontSize: 9, fill: 'var(--txt-2)', pointerEvents: 'none' }}>
                        {node.label}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      )}

      {selected && byId.get(selected) && (
        <div style={{ padding: 'var(--s3)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)' }}>
          <div style={{ fontSize: 12.5, fontWeight: 600 }}>{byId.get(selected)!.label}</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-2)', marginTop: 2 }}>
            {byId.get(selected)!.path ?? 'dangling link — no file'} ·{' '}
            {byId.get(selected)!.inDegree} in · {byId.get(selected)!.outDegree} out
            {byId.get(selected)!.fileCount > 1 && ` · ${byId.get(selected)!.fileCount} files share this name`}
          </div>
        </div>
      )}
    </div>
  );
}
