/**
 * The shared skeleton behind Projects / Hackathons / Courses / Business
 * (PRD §20–§23).
 *
 * Those four pages were near-identical copies of the same load/error/empty/grid
 * ladder. Building out the per-section actions would have meant maintaining four
 * copies of it, so the ladder lives here and each page supplies only what is
 * actually different: how to load, what actions a card offers, and any extra
 * panels that section needs.
 */
import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import type { EntityCreateResponse } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { EntityCreateModal } from '@/components/ui/EntityCreateModal';
import type { EntityCreateField } from '@/components/ui/EntityCreateModal';
import { EntityCard } from './EntityCard';
import type { EntityAction, EntityLike } from './EntityCard';
import type { EntityKind } from '@/store/useAppStore';

export interface EntityListPageProps<T extends EntityLike> {
  title: string;
  kind: EntityKind;
  /** Shown under the title, e.g. "wiki/projects/ · raw/projects/". */
  pathHint: string;
  icon: string;
  newLabel: string;
  emptyTitle: string;
  emptyDesc: string;
  /** One-line honesty note in the page footer. */
  safetyNote: React.ReactNode;
  load: () => Promise<T[]>;
  actionsFor: (item: T) => EntityAction[];
  create?: {
    fields: EntityCreateField[];
    note: string;
    submit: (values: Record<string, string>) => Promise<EntityCreateResponse>;
  };
  /** Rendered between the header and the grid (e.g. the business pipeline). */
  children?: React.ReactNode;
  /** Rendered under a specific card, keyed by entity id. */
  renderExtra?: (item: T) => React.ReactNode;
}

export function EntityListPage<T extends EntityLike>({
  title, kind, pathHint, icon, newLabel, emptyTitle, emptyDesc, safetyNote,
  load, actionsFor, create, children, renderExtra,
}: EntityListPageProps<T>) {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const showToast = useAppStore((s) => s.showToast);
  const consumeEntityCreateTarget = useAppStore((s) => s.consumeEntityCreateTarget);

  const [items, setItems] = useState<T[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<EntityCreateResponse | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await load());
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load ${title.toLowerCase()}.`);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [load, title]);

  useEffect(() => { refresh(); }, [refresh]);

  // A "New <entity>" quick action from the dashboard or ⌘K palette lands here.
  useEffect(() => {
    if (consumeEntityCreateTarget(kind)) setCreateOpen(true);
  }, [consumeEntityCreateTarget, kind]);

  const vaultPath = backendConfig?.vaultPath ?? null;
  const described = (items ?? []).filter((i) => i.status && i.status !== 'unknown').length;

  async function handleCreate(values: Record<string, string>) {
    if (!create) return;
    setCreateLoading(true);
    setCreateError(null);
    setCreateResult(null);
    try {
      const result = await create.submit(values);
      setCreateResult(result);
      if (result.ok) refresh();
      else setCreateError(result.stderr || `${title} creation failed.`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : `${title} creation failed.`);
    } finally {
      setCreateLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{title}</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            {pathHint} — {vaultPath ?? '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          {create && (
            <button className="btn btn-sm btn-primary"
                    onClick={() => { setCreateOpen(true); setCreateError(null); setCreateResult(null); }}>
              <Icon name="plus" size={13} />{newLabel}
            </button>
          )}
          <button className="btn btn-sm btn-ghost" onClick={refresh} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={refresh}>Retry</button>
        </div>
      )}

      {children}

      {items !== null && items.length > 0 && described === 0 && (
        <div style={{ padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <Icon name="doc" size={13} style={{ color: 'var(--txt-2)', marginTop: 2, flexShrink: 0 }} />
          <span>
            None of these notes declare metadata yet. Add YAML frontmatter at the top of a wiki
            note — <span className="mono">status</span>, <span className="mono">repo_path</span>,{' '}
            <span className="mono">github_url</span>, <span className="mono">demo_url</span> — and it
            appears here. Editing it in Obsidian works exactly the same as editing it from this app.
          </span>
        </div>
      )}

      {loading && items === null && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {!loading && items !== null && items.length === 0 && (
        <EmptyState
          icon={icon}
          title={emptyTitle}
          desc={emptyDesc}
          action={create ? <button className="btn btn-sm btn-primary" onClick={() => setCreateOpen(true)}>{newLabel}</button> : undefined}
        />
      )}

      {items !== null && items.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 'var(--s4)' }}>
          {items.map((item) => (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <EntityCard entity={item} vaultPath={vaultPath} actions={actionsFor(item)} onShowToast={showToast} />
              {renderExtra?.(item)}
            </div>
          ))}
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          {items.length} item{items.length === 1 ? '' : 's'} · {described} with declared status
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'flex-start', gap: 6, lineHeight: 1.5 }}>
        <Icon name="shield" size={12} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>{safetyNote}</span>
      </div>

      {createOpen && create && (
        <EntityCreateModal
          title={newLabel}
          safetyNote={create.note}
          fields={create.fields}
          loading={createLoading}
          error={createError}
          result={createResult}
          submitLabel={newLabel}
          onSubmit={handleCreate}
          onCancel={() => { if (!createLoading) setCreateOpen(false); }}
        />
      )}
    </div>
  );
}
