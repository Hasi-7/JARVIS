/**
 * Business — PRD §23.
 *
 * §23 names ops/business-pipeline.md as first-class storage. It was append-only:
 * create_business_area wrote rows and nothing ever read them back, so business
 * entities carried no status and the pipeline was invisible. It is now read and
 * rendered alongside the area cards.
 */
import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultBusinessItem, BusinessPipelineResponse } from '@/lib/api';
import { EntityListPage } from '@/components/entities/EntityListPage';
import type { EntityAction } from '@/components/entities/EntityCard';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { StatusDot } from '@/components/ui/StatusDot';

/** §23 source types. Legal and finance need review before routing. */
const REVIEW_REQUIRED = new Set(['legal', 'finance']);

const SOURCE_TYPES = [
  'ideas', 'market-research', 'customer-discovery', 'pitches', 'finance',
  'legal', 'sales', 'content', 'notes', 'screenshots', 'emails',
  'browser-research', 'chat-sessions',
];

function statusTone(status: string): 'live' | 'green' | 'amber' | 'grey' {
  switch (status.toLowerCase()) {
    case 'active':    return 'live';
    case 'shipped':   return 'green';
    case 'exploring':
    case 'paused':    return 'amber';
    default:          return 'grey';
  }
}

function PipelinePanel() {
  const [pipeline, setPipeline] = useState<BusinessPipelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getBusinessPipeline()
      .then(setPipeline)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not read the pipeline.'));
  }, []);

  if (error) return null;

  return (
    <div className="panel panel-pad">
      <PanelHeader
        icon="chart"
        title="Business pipeline"
        sub={pipeline?.path ?? 'ops/business-pipeline.md'}
      />
      {pipeline === null ? (
        <div style={{ fontSize: 11.5, color: 'var(--txt-3)' }}>Loading…</div>
      ) : !pipeline.exists ? (
        <div style={{ fontSize: 11.5, color: 'var(--txt-2)', lineHeight: 1.5 }}>
          No pipeline file yet. It is created the first time you add a business area.
        </div>
      ) : pipeline.parseMode !== 'markdown-table' ? (
        <div style={{ fontSize: 11.5, color: 'var(--amber)', lineHeight: 1.5 }}>
          The pipeline file exists but has no readable table ({pipeline.parseMode}). Open it in
          Obsidian to check its formatting — nothing has been changed.
        </div>
      ) : pipeline.items.length === 0 ? (
        <div style={{ fontSize: 11.5, color: 'var(--txt-3)' }}>Table is empty.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {pipeline.items.map((item) => (
            <div key={item.id} style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 11.5 }}>
              <StatusDot tone={statusTone(item.status)} />
              <span style={{ color: 'var(--txt-0)', fontWeight: 600, minWidth: 130 }}>{item.name}</span>
              <span style={{ color: 'var(--txt-2)', minWidth: 74 }}>{item.status}</span>
              <span style={{ flex: 1, color: 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.description}
              </span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{item.created}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function BusinessPage() {
  const navigate = useAppStore((s) => s.navigate);

  const load = useCallback(async () => (await api.getVaultBusiness()).entities, []);

  const actionsFor = useCallback((): EntityAction[] => [
    { label: 'Upload source', title: 'Route business material through the Raw Inbox', onClick: () => navigate('inbox') },
    { label: 'Research', title: 'Time-boxed market or customer research', onClick: () => navigate('research') },
    { label: 'Consolidate', title: 'Bring AI chat work into the vault', onClick: () => navigate('consolidate') },
    { label: 'Email intake', title: 'Import business leads and receipts', onClick: () => navigate('email') },
  ], [navigate]);

  return (
    <EntityListPage<VaultBusinessItem>
      title="Business"
      kind="business"
      pathHint="wiki/business/ · raw/business/ · ops/business-pipeline.md"
      icon="chart"
      newLabel="New Business Area"
      emptyTitle="No business areas found"
      emptyDesc="No .md files in wiki/business/ and no folders in raw/business/. Create an area or route business files from the Raw Inbox."
      safetyNote={
        <>
          Business files are never forced into project, hackathon or course categories.{' '}
          <strong>Legal and finance sources require review before routing</strong> (§23) — they are
          never batch-approved. Source types: <span className="mono">{SOURCE_TYPES.join(', ')}</span>.
        </>
      }
      load={load}
      actionsFor={actionsFor}
      create={{
        note: 'Creates wiki/business/<name>.md, raw/business/<name>/, and appends a row to ops/business-pipeline.md.',
        fields: [
          { key: 'name', label: 'Name', placeholder: 'Business area name', required: true },
          { key: 'description', label: 'Description', placeholder: 'Optional summary', multiline: true },
        ],
        submit: (values) => api.createBusinessArea({
          name: values.name.trim(),
          description: values.description?.trim() || undefined,
        }),
      }}
    >
      <PipelinePanel />
    </EntityListPage>
  );
}

export { REVIEW_REQUIRED };
