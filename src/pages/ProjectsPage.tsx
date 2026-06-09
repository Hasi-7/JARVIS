import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { EntityCreateResponse, VaultProject } from '@/lib/api';
import { createObsidianOpenUrl } from '@/lib/obsidian';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState } from '@/components/ui/EmptyState';
import { EntityCreateModal } from '@/components/ui/EntityCreateModal';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function truncate(text: string | null, n = 180): string {
  if (!text) return '';
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text;
}

function ProjectCard({ project, vaultPath }: { project: VaultProject; vaultPath: string | null }) {
  const obsidianUrl =
    vaultPath && project.wikiPath
      ? createObsidianOpenUrl(vaultPath, project.wikiPath)
      : null;

  return (
    <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', minHeight: 120 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--txt-0)', lineHeight: 1.3 }}>
        {project.name}
      </div>

      {project.wikiPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="doc" size={11} style={{ color: 'var(--live)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--live)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={project.wikiPath}>
            {project.wikiPath}
          </span>
        </div>
      )}
      {project.rawPath && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="folder" size={11} style={{ color: 'var(--violet)', flexShrink: 0 }} />
          <span className="mono" style={{ fontSize: 10, color: 'var(--violet)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={project.rawPath}>
            {project.rawPath}
          </span>
        </div>
      )}

      {project.preview && (
        <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5, flex: 1 }}>
          {truncate(project.preview)}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 'var(--s2)' }}>
        <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>{fmtDate(project.lastModified)}</span>

        {obsidianUrl ? (
          <a
            href={obsidianUrl}
            className="btn btn-sm btn-ghost"
            style={{ fontSize: 10.5, padding: '2px 7px', textDecoration: 'none' }}
            title="Open this note in Obsidian"
          >
            Open note
          </a>
        ) : project.rawPath && !project.wikiPath ? (
          <button className="btn btn-sm btn-ghost" disabled style={{ fontSize: 10.5, padding: '2px 7px', opacity: 0.35 }} title="No wiki note — raw folder only">
            Raw folder
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function ProjectsPage() {
  const backendConfig = useAppStore((s) => s.backendConfig);
  const [projects, setProjects] = useState<VaultProject[] | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<EntityCreateResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getVaultProjects();
      setProjects(res.projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects.');
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const vaultPath = backendConfig?.vaultPath ?? null;

  async function handleCreate(values: Record<string, string>) {
    setCreateLoading(true);
    setCreateError(null);
    setCreateResult(null);
    try {
      const result = await api.createProject({
        name: values.name.trim(),
      });
      setCreateResult(result);
      if (result.ok) load();
      else setCreateError(result.stderr || 'Project creation failed.');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Project creation failed.');
    } finally {
      setCreateLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s3)' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Projects</div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
            wiki/projects/ · raw/projects/ — {vaultPath ?? '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
          <button className="btn btn-sm btn-primary" onClick={() => { setCreateOpen(true); setCreateError(null); setCreateResult(null); }}>
            <Icon name="plus" size={13} />
            New Project
          </button>
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>
            <Icon name="sync" size={13} style={{ animation: loading ? 'spin 1s linear infinite' : undefined }} />
            Refresh
          </button>
        </div>
      </div>

      {/* error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* loading skeleton */}
      {loading && projects === null && (
        <div style={{ textAlign: 'center', padding: 'var(--s8)', color: 'var(--txt-3)', fontSize: 12 }}>
          Loading vault…
        </div>
      )}

      {/* empty */}
      {!loading && projects !== null && projects.length === 0 && (
        <EmptyState
          icon="cube"
          title="No projects found"
          desc="No .md files in wiki/projects/ and no folders in raw/projects/. Create a project or route project files from the Raw Inbox."
          action={<button className="btn btn-sm btn-primary" onClick={() => setCreateOpen(true)}>New Project</button>}
        />
      )}

      {/* cards */}
      {projects !== null && projects.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--s4)' }}>
          {projects.map((p) => <ProjectCard key={p.id} project={p} vaultPath={vaultPath} />)}
        </div>
      )}

      {/* count */}
      {projects !== null && projects.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
          {projects.length} project{projects.length === 1 ? '' : 's'} found
        </div>
      )}

      {/* footer */}
      <div style={{ fontSize: 11, color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={12} />
        New Project runs the safe brain command for this entity type. "Open note" links open Obsidian.
      </div>

      {createOpen && (
        <EntityCreateModal
          title="New Project"
          safetyNote="Creates the project using `brain new-project <name>`. Repo linking can be added later."
          fields={[
            { key: 'name', label: 'Name', placeholder: 'Project name', required: true },
          ]}
          loading={createLoading}
          error={createError}
          result={createResult}
          submitLabel="Create project"
          onSubmit={handleCreate}
          onCancel={() => { if (!createLoading) setCreateOpen(false); }}
        />
      )}

    </div>
  );
}
