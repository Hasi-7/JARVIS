/**
 * Shared entity card for Projects / Hackathons / Courses / Business
 * (PRD §20–§23).
 *
 * The four pages were read-only lists of name + path + preview, because the
 * backend model carried nothing else. Now that notes can declare status, repo
 * path and links in frontmatter, this renders those and offers the actions each
 * section asks for.
 *
 * Actions that mutate anything go through the approval queue — this component
 * only ever queues a request or copies a command for the user to run.
 */
import { useState } from 'react';
import type { VaultEntityMetadata } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { createObsidianOpenUrl } from '@/lib/obsidian';

export interface EntityLike extends VaultEntityMetadata {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  lastModified: string | null;
  preview: string | null;
}

export interface EntityAction {
  label: string;
  /** Copies this string to the clipboard instead of running anything. */
  copy?: string;
  onClick?: () => void;
  title?: string;
}

function statusTone(status: string | null): 'green' | 'amber' | 'grey' | 'live' {
  switch ((status ?? '').toLowerCase()) {
    case 'active':   return 'live';
    case 'shipped':  return 'green';
    case 'paused':
    case 'blocked':  return 'amber';
    default:         return 'grey';
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function truncate(text: string | null, n = 160): string {
  if (!text) return '';
  return text.length > n ? `${text.slice(0, n).trimEnd()}…` : text;
}

export function EntityCard({ entity, vaultPath, actions = [], onShowToast }: {
  entity: EntityLike;
  vaultPath: string | null;
  actions?: EntityAction[];
  onShowToast?: (msg: string) => void;
}) {
  const [copied, setCopied] = useState<string | null>(null);

  const obsidianUrl = vaultPath && entity.wikiPath
    ? createObsidianOpenUrl(vaultPath, entity.wikiPath)
    : null;

  async function copy(action: EntityAction) {
    if (!action.copy) { action.onClick?.(); return; }
    try {
      await navigator.clipboard.writeText(action.copy);
      setCopied(action.label);
      onShowToast?.(`${action.label} copied. Run it yourself — this app never launches it.`);
      window.setTimeout(() => setCopied(null), 1800);
    } catch {
      onShowToast?.('Could not copy — check browser permissions.');
    }
  }

  return (
    <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', minHeight: 150 }}>

      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <StatusDot tone={statusTone(entity.status)} />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--txt-0)', lineHeight: 1.3, flex: 1 }}>
          {entity.name}
        </span>
        {entity.status && entity.status !== 'unknown' && (
          <span style={{ fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--txt-2)' }}>
            {entity.status}
          </span>
        )}
      </div>

      {entity.frontmatterError && (
        <div style={{ fontSize: 10.5, color: 'var(--amber)', lineHeight: 1.4 }}>
          <Icon name="shield" size={11} style={{ verticalAlign: '-1px', marginRight: 4 }} />
          Frontmatter could not be read: {entity.frontmatterError}
        </div>
      )}

      {/* links + paths */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {entity.wikiPath && (
          <Row icon="doc" color="var(--live)" text={entity.wikiPath} />
        )}
        {entity.rawPath && (
          <Row icon="folder" color="var(--violet)" text={entity.rawPath} />
        )}
        {entity.repoPath && (
          <Row icon="cube" color="var(--txt-2)" text={entity.repoPath} />
        )}
      </div>

      {(entity.githubUrl || entity.demoUrl) && (
        <div style={{ display: 'flex', gap: 'var(--s3)', flexWrap: 'wrap' }}>
          {entity.githubUrl && (
            <a href={entity.githubUrl} target="_blank" rel="noreferrer"
               style={{ fontSize: 10.5, color: 'var(--live)' }}>GitHub ↗</a>
          )}
          {entity.demoUrl && (
            <a href={entity.demoUrl} target="_blank" rel="noreferrer"
               style={{ fontSize: 10.5, color: 'var(--live)' }}>Demo ↗</a>
          )}
        </div>
      )}

      {entity.preview && (
        <div style={{ fontSize: 11, color: 'var(--txt-2)', lineHeight: 1.5, flex: 1 }}>
          {truncate(entity.preview)}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 'auto', paddingTop: 'var(--s2)' }}>
        <span style={{ fontSize: 10, color: 'var(--txt-3)' }}>{fmtDate(entity.lastModified)}</span>
        <div style={{ flex: 1 }} />
        {obsidianUrl && (
          <a href={obsidianUrl} className="btn btn-sm btn-ghost"
             style={{ fontSize: 10.5, padding: '2px 7px', textDecoration: 'none' }}
             title="Open this note in Obsidian">
            Open note
          </a>
        )}
        {actions.map((a) => (
          <button key={a.label} className="btn btn-sm btn-ghost"
                  style={{ fontSize: 10.5, padding: '2px 7px' }}
                  title={a.title ?? (a.copy ? 'Copy this command to run yourself' : undefined)}
                  onClick={() => copy(a)}>
            {copied === a.label ? 'Copied!' : a.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Row({ icon, color, text }: { icon: string; color: string; text: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <Icon name={icon} size={11} style={{ color, flexShrink: 0 }} />
      <span className="mono" title={text}
            style={{ fontSize: 10, color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {text}
      </span>
    </div>
  );
}
