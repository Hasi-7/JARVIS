import React, { useCallback, useEffect, useState } from 'react';
import {
  TODAY, SYSTEM, AGENT_STATES, AGENT_MODES,
  QUICK_ACTIONS,
} from '@/data/mock';
import { useAppStore } from '@/store/useAppStore';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';
import { StatusCard } from '@/components/dashboard/StatusCard';
import { SystemRow } from '@/components/dashboard/SystemRow';
import { api } from '@/lib/api';
import type {
  DashboardSummary,
  DashboardTodayPlanItem,
  DashboardActiveWork,
  DashboardActiveWorkBackfillItem,
  DashboardActiveWorkEscalationItem,
  ConversationSummary,
} from '@/lib/api';
import type { RouteId, SystemService } from '@/types';

function taskStatusColor(status: string): string {
  if (status === 'blocked')     return 'var(--red)';
  if (status === 'in progress') return 'var(--live)';
  return 'var(--txt-3)';
}

function taskStatusBg(status: string): string {
  if (status === 'in progress') return 'var(--live-bg)';
  if (status === 'blocked')     return 'var(--red-bg)';
  return 'transparent';
}

function taskStatusBorder(status: string): string {
  if (status === 'in progress') return '1px solid var(--live-line)';
  if (status === 'blocked')     return '1px solid var(--red-line)';
  return '1px solid transparent';
}

// ── Today's plan panel ────────────────────────────────────────────────────────

function TodayPlanPanel({
  loading,
  items,
  failed,
  onNavigateTasks,
}: {
  loading: boolean;
  items: DashboardTodayPlanItem[] | null;
  failed: boolean;
  onNavigateTasks: () => void;
}) {
  const planCount = items?.length ?? 0;

  return (
    <div className="panel panel-pad">
      <PanelHeader
        icon="sun"
        title="Today's plan"
        sub={
          loading ? 'Loading…' :
          failed   ? 'unavailable' :
          items === null ? undefined :
          planCount === 0 ? 'no active tasks' :
          `${planCount} active task${planCount === 1 ? '' : 's'}`
        }
        right={
          <button className="btn btn-sm btn-ghost" onClick={onNavigateTasks}>
            All tasks <Icon name="chevron" size={13} />
          </button>
        }
      />

      {loading ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 4 }}>Loading…</div>
      ) : failed ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 4 }}>
          Could not load tasks — backend unavailable.{' '}
          <button className="btn btn-sm btn-ghost" style={{ display: 'inline' }} onClick={onNavigateTasks}>
            Open Tasks
          </button>
        </div>
      ) : items !== null && items.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', alignItems: 'flex-start', paddingTop: 4 }}>
          <span style={{ color: 'var(--txt-3)', fontSize: 12 }}>No active tasks found.</span>
          <button className="btn btn-sm" onClick={onNavigateTasks}>
            <Icon name="check" size={13} /> Open Tasks
          </button>
        </div>
      ) : items !== null ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {items.map((item) => (
            <button
              key={item.id}
              className="btn"
              onClick={onNavigateTasks}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto',
                alignItems: 'center',
                gap: 'var(--s3)',
                padding: '9px 12px',
                background: taskStatusBg(item.status),
                border: taskStatusBorder(item.status),
                textAlign: 'left',
                width: '100%',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: taskStatusColor(item.status),
                    }}
                  >
                    {item.reason}
                  </span>
                  {item.priority === 'high' && (
                    <span style={{ fontSize: 10, color: 'var(--amber)', fontWeight: 600 }}>↑ high</span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--txt-0)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {item.title}
                </div>
                {(item.area || item.due) && (
                  <div style={{ display: 'flex', gap: 10, marginTop: 3 }}>
                    {item.area && (
                      <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>{item.area}</span>
                    )}
                    {item.due && (
                      <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>
                        due {item.due}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <Icon name="chevron" size={12} style={{ color: 'var(--txt-3)', flexShrink: 0 }} />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ── Recent AI work panel ──────────────────────────────────────────────────────

function convRelTime(iso: string): string {
  try {
    const d = new Date(iso);
    const diffH = (Date.now() - d.getTime()) / 3_600_000;
    if (diffH < 24) return d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false });
    if (diffH < 48) return 'Yesterday';
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

function RecentAiWorkPanel({
  loading,
  convs,
  failed,
  onNavigateAgent,
  onOpenConversation,
}: {
  loading: boolean;
  convs: ConversationSummary[] | null;
  failed: boolean;
  onNavigateAgent: () => void;
  onOpenConversation: (id: string) => void;
}) {
  const items = convs
    ? [...convs].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 5)
    : null;

  return (
    <div className="panel panel-pad">
      <PanelHeader
        icon="merge"
        title="Recent AI work"
        sub={
          loading ? 'Loading…' :
          failed   ? 'unavailable' :
          items !== null ? `${items.length} conversation${items.length === 1 ? '' : 's'}` :
          undefined
        }
        right={
          <button className="btn btn-sm btn-ghost" onClick={onNavigateAgent}>
            <Icon name="chevron" size={13} />
          </button>
        }
      />

      {loading ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 4 }}>Loading…</div>
      ) : failed ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 4 }}>
          Could not load conversations.{' '}
          <button className="btn btn-sm btn-ghost" style={{ display: 'inline' }} onClick={onNavigateAgent}>
            Open Local Agent
          </button>
        </div>
      ) : items !== null && items.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', alignItems: 'flex-start', paddingTop: 4 }}>
          <span style={{ color: 'var(--txt-3)', fontSize: 12 }}>No recent local-agent conversations.</span>
          <button className="btn btn-sm" onClick={onNavigateAgent}>
            <Icon name="merge" size={13} /> Open Local Agent
          </button>
        </div>
      ) : items !== null ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {items.map((conv) => (
            <button
              key={conv.id}
              className="btn"
              onClick={() => onOpenConversation(conv.id)}
              title="Open this conversation in Local Agent"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto',
                alignItems: 'center',
                gap: 'var(--s3)',
                padding: '8px 10px',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--txt-0)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {conv.title}
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 2 }}>
                  Local Agent · {conv.messageCount} msg{conv.messageCount === 1 ? '' : 's'}
                </div>
              </div>
              <span style={{ fontSize: 10.5, color: 'var(--txt-3)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {convRelTime(conv.updatedAt)}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ── Active Work panel ─────────────────────────────────────────────────────────

type ActiveWorkNavId = 'backfill' | 'escalation' | 'resume' | 'calendar' | 'inbox';

interface ActiveWorkGroup<T> {
  label:    string;
  icon:     string;
  nav:      ActiveWorkNavId;
  items:    T[];
  renderItem: (item: T) => React.ReactNode;
}

function statusChipStyle(status: string): React.CSSProperties {
  if (status === 'blocked')     return { color: 'var(--red)',    background: 'var(--red-bg)',  border: '1px solid var(--red-line)' };
  if (status === 'in-progress') return { color: 'var(--live)',   background: 'var(--live-bg)', border: '1px solid var(--live-line)' };
  if (status === 'interview')   return { color: 'var(--violet)', background: 'transparent',   border: '1px solid var(--violet)' };
  if (status === 'ready')       return { color: 'var(--green)',  background: 'transparent',   border: '1px solid var(--green)' };
  return { color: 'var(--txt-3)', background: 'transparent', border: '1px solid var(--line)' };
}

function priorityChip(priority: string | null | undefined): React.ReactNode {
  if (!priority) return null;
  const color = priority === 'high' ? 'var(--amber)' : priority === 'low' ? 'var(--txt-3)' : 'var(--txt-2)';
  return (
    <span style={{ fontSize: 10, fontWeight: 600, color, marginLeft: 4 }}>
      {priority === 'high' ? '↑' : priority === 'low' ? '↓' : '·'} {priority}
    </span>
  );
}

function ActiveWorkRow({
  children,
  onClick,
  action,
}: {
  children: React.ReactNode;
  onClick: () => void;
  action?: React.ReactNode;
}) {
  return (
    <div
      className="btn"
      onClick={onClick}
      role="button"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '7px 10px',
        textAlign: 'left',
        width: '100%',
        borderBottom: '1px solid var(--line-soft)',
        borderRadius: 0,
        cursor: 'pointer',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 2,
          minWidth: 0,
          flex: 1,
        }}
      >
        {children}
      </div>
      {action && (
        // Stop the click from bubbling to the row's navigate handler.
        <div style={{ flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
          {action}
        </div>
      )}
    </div>
  );
}

// ── quick-action (mark done) types ────────────────────────────────────────────

type PendingMarkDone =
  | { kind: 'backfill';   item: DashboardActiveWorkBackfillItem }
  | { kind: 'escalation'; item: DashboardActiveWorkEscalationItem };

function MarkDoneConfirmModal({
  pending,
  loading,
  error,
  onConfirm,
  onCancel,
}: {
  pending:   PendingMarkDone;
  loading:   boolean;
  error:     string | null;
  onConfirm: () => void;
  onCancel:  () => void;
}) {
  const isBackfill = pending.kind === 'backfill';
  const source     = isBackfill ? 'ops/backfill.md' : 'ops/escalation-queue.md';
  const question   = isBackfill ? 'Mark this Backfill item as done?' : 'Mark this Escalation as done?';
  const body       = `This updates only the status cell in ${source}. The backend creates a backup before writing.`;

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div className="panel" style={{
        width: 440, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>{question}</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          <div style={{ fontSize: 12.5, color: 'var(--txt-0)', fontWeight: 500 }}>
            {pending.item.title}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span style={{ color: 'var(--txt-2)' }}>{pending.item.status}</span>
            <Icon name="arrow-right" size={12} style={{ color: 'var(--txt-3)' }} />
            <span style={{ color: 'var(--green)', fontWeight: 600 }}>done</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>
            Source: <span className="mono" style={{ fontSize: 10.5 }}>{source}</span>
          </div>
        </div>

        <div style={{
          fontSize: 11, color: 'var(--txt-2)',
          padding: 'var(--s2) var(--s3)',
          background: 'var(--surface-2)', borderRadius: 'var(--r2)',
          border: '1px solid var(--line)',
        }}>
          {body}
        </div>

        {error && (
          <div style={{
            fontSize: 11.5, color: 'var(--red)',
            padding: 'var(--s2) var(--s3)',
            background: 'var(--red-bg)', borderRadius: 'var(--r2)',
            border: '1px solid var(--red-line)',
          }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
          <button className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-sm btn-primary" onClick={onConfirm} disabled={loading}>
            {loading ? 'Saving…' : 'Mark done'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ActiveWorkGroupSection<T>({
  group,
  onNavigate,
}: {
  group: ActiveWorkGroup<T>;
  onNavigate: (nav: ActiveWorkNavId) => void;
}) {
  if (group.items.length === 0) return null;
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px 4px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name={group.icon as Parameters<typeof Icon>[0]['name']} size={12} style={{ color: 'var(--txt-3)' }} />
          <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--txt-2)' }}>
            {group.label}
          </span>
          <span style={{
            fontSize: 10,
            background: 'var(--surface-2)',
            border: '1px solid var(--line)',
            borderRadius: 3,
            padding: '0 4px',
            color: 'var(--txt-3)',
          }}>
            {group.items.length}
          </span>
        </div>
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => onNavigate(group.nav)}
          style={{ fontSize: 11, padding: '2px 6px' }}
        >
          View all <Icon name="chevron" size={11} />
        </button>
      </div>
      <div>
        {group.items.map((item, i) => (
          <div key={i} onClick={() => onNavigate(group.nav)}>
            {group.renderItem(item)}
          </div>
        ))}
      </div>
    </div>
  );
}

function ActiveWorkPanel({
  loading,
  activeWork,
  failed,
  onNavigate,
  onReload,
  showToast,
}: {
  loading:    boolean;
  activeWork: DashboardActiveWork | null;
  failed:     boolean;
  onNavigate: (nav: ActiveWorkNavId) => void;
  onReload:   () => Promise<void> | void;
  showToast:  (msg: string) => void;
}) {
  // ── quick action: mark backfill / escalation item done ─────────────────────
  const [pending,    setPending]    = useState<PendingMarkDone | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  function openMarkDone(p: PendingMarkDone) {
    setActionError(null);
    setPending(p);
  }

  async function confirmMarkDone() {
    if (!pending) return;
    setSubmitting(true);
    setActionError(null);
    try {
      if (pending.kind === 'backfill') {
        await api.updateBackfillStatus(pending.item.id, 'done');
      } else {
        await api.updateEscalationStatus(pending.item.id, 'done');
      }
      setPending(null);
      showToast('Marked done.');
      await onReload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update status.');
    } finally {
      setSubmitting(false);
    }
  }

  const markDoneButton = (p: PendingMarkDone) => (
    <button
      className="btn btn-sm btn-ghost"
      style={{ fontSize: 10.5, padding: '2px 8px', whiteSpace: 'nowrap' }}
      onClick={() => openMarkDone(p)}
      disabled={submitting}
      title="Mark this item as done"
    >
      <Icon name="check" size={11} style={{ marginRight: 3 }} />
      Mark done
    </button>
  );

  const totalItems = activeWork
    ? activeWork.backfill.length + activeWork.escalations.length +
      activeWork.resume.length + activeWork.calendar.length + activeWork.raw.length
    : 0;

  const groups: ActiveWorkGroup<unknown>[] = activeWork ? [
    {
      label: 'Backfill',
      icon: 'layers',
      nav: 'backfill',
      items: activeWork.backfill,
      renderItem: (item) => {
        const it = item as DashboardActiveWorkBackfillItem;
        return (
          <ActiveWorkRow
            onClick={() => onNavigate('backfill')}
            action={markDoneButton({ kind: 'backfill', item: it })}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
                  ...statusChipStyle(it.status),
                }}
              >
                {it.reason}
              </span>
              {priorityChip(it.priority)}
              {it.type && (
                <span style={{ fontSize: 10, color: 'var(--txt-3)', marginLeft: 'auto' }}>{it.type}</span>
              )}
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
              {it.title}
            </span>
          </ActiveWorkRow>
        );
      },
    },
    {
      label: 'Escalations',
      icon: 'bolt',
      nav: 'escalation',
      items: activeWork.escalations,
      renderItem: (item) => {
        const it = item as DashboardActiveWorkEscalationItem;
        return (
          <ActiveWorkRow
            onClick={() => onNavigate('escalation')}
            action={markDoneButton({ kind: 'escalation', item: it })}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
                  ...statusChipStyle(it.status),
                }}
              >
                {it.reason}
              </span>
              {priorityChip(it.priority)}
              {it.target && (
                <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{it.target}</span>
              )}
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
              {it.title}
            </span>
          </ActiveWorkRow>
        );
      },
    },
    {
      label: 'Resume',
      icon: 'doc',
      nav: 'resume',
      items: activeWork.resume,
      renderItem: (item) => {
        const it = item as import('@/lib/api').DashboardActiveWorkResumeItem;
        return (
          <ActiveWorkRow onClick={() => onNavigate('resume')}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
                  ...statusChipStyle(it.status),
                }}
              >
                {it.reason}
              </span>
              {priorityChip(it.priority)}
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
              {it.title}
            </span>
            {(it.company || it.role) && (
              <span style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>
                {[it.company, it.role].filter(Boolean).join(' · ')}
              </span>
            )}
          </ActiveWorkRow>
        );
      },
    },
    {
      label: 'Calendar',
      icon: 'cal',
      nav: 'calendar',
      items: activeWork.calendar,
      renderItem: (item) => {
        const it = item as import('@/lib/api').DashboardActiveWorkCalendarItem;
        return (
          <ActiveWorkRow onClick={() => onNavigate('calendar')}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 3, color: 'var(--amber)', border: '1px solid var(--amber)', background: 'transparent' }}>
                {it.reason}
              </span>
              {it.date && (
                <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>{it.date}{it.time ? ` ${it.time}` : ''}</span>
              )}
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
              {it.title}
            </span>
          </ActiveWorkRow>
        );
      },
    },
    {
      label: 'Raw Inbox',
      icon: 'upload',
      nav: 'inbox',
      items: activeWork.raw,
      renderItem: (item) => {
        const it = item as import('@/lib/api').DashboardActiveWorkRawItem;
        return (
          <ActiveWorkRow onClick={() => onNavigate('inbox')}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
                  color: it.status === 'edited' ? 'var(--amber)' : 'var(--txt-2)',
                  border: `1px solid ${it.status === 'edited' ? 'var(--amber)' : 'var(--line)'}`,
                  background: 'transparent',
                }}
              >
                {it.reason}
              </span>
            </div>
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--txt-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
              {it.title}
            </span>
          </ActiveWorkRow>
        );
      },
    },
  ] : [];

  const visibleGroups = groups.filter((g) => g.items.length > 0);

  return (
    <>
    <div className="panel" style={{ overflow: 'hidden' }}>
      <div style={{ padding: 'var(--s4) var(--s4) var(--s3)' }}>
        <PanelHeader
          icon="merge"
          title="Active work"
          sub={
            loading ? 'Loading…' :
            failed   ? 'unavailable' :
            activeWork === null ? undefined :
            totalItems === 0 ? 'no active items' :
            `${totalItems} item${totalItems === 1 ? '' : 's'} need attention`
          }
        />
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, padding: '0 var(--s4) var(--s4)' }}>Loading…</div>
      ) : failed ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, padding: '0 var(--s4) var(--s4)' }}>
          Could not load active work — backend unavailable.
        </div>
      ) : activeWork !== null && visibleGroups.length === 0 ? (
        <div style={{ color: 'var(--txt-3)', fontSize: 12, padding: '0 var(--s4) var(--s4)' }}>
          No active work items found.
        </div>
      ) : activeWork !== null ? (
        <div style={{ borderTop: '1px solid var(--line-soft)' }}>
          {visibleGroups.map((g) => (
            <ActiveWorkGroupSection
              key={g.label}
              group={g}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ) : null}
    </div>

    {pending && (
      <MarkDoneConfirmModal
        pending={pending}
        loading={submitting}
        error={actionError}
        onConfirm={confirmMarkDone}
        onCancel={() => { if (!submitting) setPending(null); }}
      />
    )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

const BRAIN_ACTION_MAP: Record<string, string> = {
  today:     'today',
  weekly:    'weekly',
  syncraw:   'sync-raw',
  calexport: 'calendar-export',
};

export function DashboardPage() {
  const agentState      = useAppStore((s) => s.agentState);
  const agentMode       = useAppStore((s) => s.agentMode);
  const setAgentMode    = useAppStore((s) => s.setAgentMode);
  const navigate        = useAppStore((s) => s.navigate);
  const showToast       = useAppStore((s) => s.showToast);
  const settings        = useAppStore((s) => s.settings);
  const backendStatus   = useAppStore((s) => s.backendStatus);
  const backendConfig   = useAppStore((s) => s.backendConfig);
  const cmdLog          = useAppStore((s) => s.cmdLog);
  const runBrainCommand = useAppStore((s) => s.runBrainCommand);
  const agentStatus     = useAppStore((s) => s.agentStatus);
  const setAgentPrefill = useAppStore((s) => s.setAgentPrefill);
  const setAgentConvTarget = useAppStore((s) => s.setAgentConvTarget);

  const [ask, setAsk] = useState('');

  // ── dashboard summary ──────────────────────────────────────────────────────
  const [summary, setSummary]           = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError]   = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await api.getDashboardSummary();
      setSummary(data);
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : 'Could not reach backend.');
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  // ── conversations (recent AI work) ─────────────────────────────────────────
  const [convs, setConvs]           = useState<ConversationSummary[] | null>(null);
  const [convsLoading, setConvsLoading] = useState(true);
  const [convsError, setConvsError]   = useState(false);

  const loadConversations = useCallback(async () => {
    setConvsLoading(true);
    setConvsError(false);
    try {
      const data = await api.listConversations();
      setConvs(data.conversations);
    } catch {
      setConvsError(true);
    } finally {
      setConvsLoading(false);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  // ── derived counts (safe to use before summary loads) ─────────────────────
  const approvalsCount = summary
    ? summary.raw.proposed + summary.raw.edited + summary.calendar.pending
    : 0;
  const rawPending  = summary?.raw.staged    ?? 0;
  const calPending  = summary?.calendar.pending ?? 0;
  const backfillActive = summary
    ? summary.backfill.new + summary.backfill.triaged + summary.backfill.inProgress
    : 0;
  const resumeActive = summary
    ? summary.resume.new + summary.resume.tailoring + summary.resume.applied + summary.resume.interview
    : 0;

  const meta = AGENT_STATES[agentState];

  const runCommand = (id: string) => {
    if (id === 'ask')         return navigate('agent');
    if (id === 'research')    return navigate('research');
    if (id === 'consolidate') return navigate('consolidate');
    if (id === 'upload')      return navigate('inbox');
    const brainCmd = BRAIN_ACTION_MAP[id];
    if (brainCmd) { runBrainCommand(brainCmd); return; }
    const a = QUICK_ACTIONS.find((x) => x.id === id);
    if (a) showToast(a.cmd ? `${a.cmd} (not wired yet)` : `Opened ${a.label}`);
  };

  const submitAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ask.trim()) return;
    setAgentPrefill(ask.trim());
    navigate('agent');
    setAsk('');
  };

  // ── count strip ────────────────────────────────────────────────────────────
  const counts = [
    {
      label: 'Approvals',
      value: summaryLoading ? '…' : approvalsCount,
      sub: 'proposals + calendar',
      tone: 'amber' as const,
      nav: 'inbox' as RouteId,
      accent: true,
    },
    {
      label: 'Raw pending',
      value: summaryLoading ? '…' : rawPending,
      sub: 'staged files',
      tone: 'live' as const,
      nav: 'inbox' as RouteId,
    },
    {
      label: 'Escalations',
      value: summaryLoading ? '…' : (summary?.escalations?.active ?? 0),
      sub: 'active items',
      tone: 'violet' as const,
      nav: 'escalation' as RouteId,
    },
    {
      label: 'Calendar',
      value: summaryLoading ? '…' : calPending,
      sub: 'pending candidates',
      tone: 'live' as const,
      nav: 'calendar' as RouteId,
    },
    {
      label: 'Backfill',
      value: summaryLoading ? '…' : backfillActive,
      sub: 'active items',
      icon: 'layers',
      nav: 'backfill' as RouteId,
    },
    {
      label: 'Resume',
      value: summaryLoading ? '…' : resumeActive,
      sub: 'in-flight',
      icon: 'doc',
      nav: 'resume' as RouteId,
    },
  ];

  // ── runtime services ───────────────────────────────────────────────────────
  const backendService: SystemService =
    backendStatus === 'ok'      ? { state: 'ready',    label: 'Backend',   detail: 'FastAPI · localhost:8000' }
    : backendStatus === 'error' ? { state: 'blocked',  label: 'Backend',   detail: 'Not connected · start uvicorn' }
    :                             { state: 'idle',     label: 'Backend',   detail: 'Checking…' };

  const brainAvail = summary?.runtime.brain;
  const brainService: SystemService =
    backendStatus !== 'ok'
      ? { state: 'disabled', label: 'Brain CLI', detail: 'Backend not connected' }
      : brainAvail === 'available'
        ? { state: 'ready',   label: 'Brain CLI', detail: backendConfig?.brainCmd ?? 'Connected' }
        : brainAvail === 'unavailable'
          ? { state: 'blocked', label: 'Brain CLI', detail: 'brain.cmd not found — check config' }
          : { state: 'idle',    label: 'Brain CLI', detail: 'Checking…' };

  const vaultExists = summary?.runtime.vaultExists;
  const vaultService: SystemService =
    backendStatus !== 'ok'
      ? { state: 'disabled', label: 'Vault',     detail: 'Backend not connected' }
      : vaultExists === true
        ? { state: 'ready',   label: 'Vault',     detail: backendConfig?.vaultPath ?? 'Connected' }
        : vaultExists === false
          ? { state: 'blocked', label: 'Vault',     detail: 'Vault path not found — check config' }
          : { state: 'idle',    label: 'Vault',     detail: 'Checking…' };

  const localModelService: SystemService =
    agentStatus === null
      ? { state: 'idle',     label: 'Local model', detail: 'Checking…' }
      : agentStatus.available
        ? { state: 'ready',  label: 'Local model', detail: `${agentStatus.model} · ${agentStatus.provider}` }
        : { state: 'partial',label: 'Local model', detail: agentStatus.message.slice(0, 52) };

  const vaultDisplay = backendConfig?.vaultPath ?? settings.vaultPath;

  // ── partial error notice ───────────────────────────────────────────────────
  const partialErrors = summary?.errors ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)', maxWidth: 1320, margin: '0 auto' }}>

      {/* ── header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--s4)', flexWrap: 'wrap' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 4 }}>
            {TODAY.date} · Good afternoon, Hasnain
          </div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: '-0.015em', color: 'var(--txt-0)' }}>
            Today's focus
          </h1>
          <div style={{ fontSize: 14, color: 'var(--txt-1)', marginTop: 2 }}>{TODAY.focus}</div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--s2)' }}>
          <button className="btn btn-sm btn-ghost" onClick={loadSummary} disabled={summaryLoading} title="Refresh metrics">
            <Icon name="sync" size={13} />
            {summaryLoading ? 'Loading…' : 'Refresh'}
          </button>
          <button className="btn" onClick={() => runCommand('today')}>
            <Icon name="sun" size={15} />Run today
          </button>
          <button className="btn" onClick={() => runCommand('weekly')}>
            <Icon name="cal" size={15} />Weekly
          </button>
          <button className="btn btn-primary" onClick={() => navigate('inbox')}>
            <Icon name="upload" size={15} />Upload raw
          </button>
        </div>
      </div>

      {/* ── backend disconnected notice ── */}
      {summaryError && (
        <div style={{
          padding: '10px 14px',
          background: 'var(--surface-2)',
          border: '1px solid var(--red)',
          borderRadius: 'var(--r2)',
          fontSize: 12,
          color: 'var(--txt-1)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <StatusDot tone="red" />
          <span>Dashboard metrics unavailable — backend not reachable. Start uvicorn and refresh.</span>
        </div>
      )}

      {/* ── partial error notice ── */}
      {!summaryError && partialErrors.length > 0 && (
        <div style={{
          padding: '8px 14px',
          background: 'var(--surface-2)',
          border: '1px solid var(--amber)',
          borderRadius: 'var(--r2)',
          fontSize: 11,
          color: 'var(--txt-2)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <StatusDot tone="amber" />
          <span>
            Some metrics could not load: {partialErrors.map((e) => e.source).join(', ')}. Counts may be incomplete.
          </span>
        </div>
      )}

      {/* ── count strip ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--s3)' }}>
        {counts.map((c) => (
          <StatusCard
            key={c.label}
            label={c.label}
            value={c.value}
            sub={c.sub}
            tone={'tone' in c ? c.tone : undefined}
            icon={'icon' in c ? c.icon : undefined}
            accent={'accent' in c ? c.accent : undefined}
            onClick={() => navigate(c.nav)}
          />
        ))}
      </div>

      {/* ── main 2-col grid ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.9fr) minmax(320px, 1fr)',
          gap: 'var(--s5)',
          alignItems: 'start',
        }}
      >
        {/* ── left column ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

          {/* today's plan — real task data */}
          <TodayPlanPanel
            loading={summaryLoading}
            items={summary?.todayPlan?.items ?? null}
            failed={!summaryLoading && summaryError !== null}
            onNavigateTasks={() => navigate('tasks')}
          />

          {/* pending approvals — real data */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="check"
              title="Pending approvals"
              sub={
                summary
                  ? `${approvalsCount} item${approvalsCount === 1 ? '' : 's'} need review`
                  : summaryLoading ? 'Loading…' : 'Could not load'
              }
            />
            {summaryLoading ? (
              <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 8 }}>Loading…</div>
            ) : summary ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {/* raw proposals */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 0', borderBottom: '1px solid var(--line-soft)',
                }}>
                  <StatusDot tone={summary.raw.proposed + summary.raw.edited > 0 ? 'amber' : 'grey'} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--txt-0)' }}>
                      {summary.raw.proposed + summary.raw.edited} raw file proposals
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--txt-2)' }}>
                      {summary.raw.proposed} proposed · {summary.raw.edited} edited
                    </div>
                  </div>
                  <button className="btn btn-sm" onClick={() => navigate('inbox')}>
                    Review <Icon name="chevron" size={12} />
                  </button>
                </div>
                {/* calendar candidates */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 0',
                }}>
                  <StatusDot tone={summary.calendar.pending > 0 ? 'amber' : 'grey'} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--txt-0)' }}>
                      {summary.calendar.pending} calendar candidates
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--txt-2)' }}>
                      {summary.calendar.approved} approved · {summary.calendar.total} total
                    </div>
                  </div>
                  <button className="btn btn-sm" onClick={() => navigate('calendar')}>
                    Review <Icon name="chevron" size={12} />
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--txt-3)', fontSize: 12, paddingTop: 8 }}>
                Could not load approvals — backend unavailable.
              </div>
            )}
          </div>

          {/* active work drill-down — real data */}
          <ActiveWorkPanel
            loading={summaryLoading}
            activeWork={summary?.activeWork ?? null}
            failed={!summaryLoading && summaryError !== null}
            onNavigate={(nav) => navigate(nav as RouteId)}
            onReload={loadSummary}
            showToast={showToast}
          />

          {/* two-up: command output + recent AI work */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s5)' }}>

            {/* command output — live from backend */}
            <div className="panel panel-pad">
              <PanelHeader icon="cmd" title="Recent command output" />
              {cmdLog.length === 0 ? (
                <div
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--txt-3)', paddingTop: 'var(--s2)' }}
                >
                  No commands run yet. Use Quick actions or ⌘K.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                  {cmdLog.map((entry, i) => (
                    <div key={i} style={{ fontSize: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <StatusDot tone={entry.ok ? 'green' : 'red'} />
                        <span className="mono" style={{ color: 'var(--txt-0)', fontSize: 11.5 }}>
                          $ {entry.cmd}
                        </span>
                        <span className="mono" style={{ marginLeft: 'auto', color: 'var(--txt-3)', fontSize: 10.5 }}>
                          {entry.at}
                        </span>
                      </div>
                      <div
                        className="mono"
                        style={{
                          fontSize: 10.5,
                          color: 'var(--txt-2)',
                          paddingLeft: 14,
                          marginTop: 2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {entry.out}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* recent AI work — real conversation history */}
            <RecentAiWorkPanel
              loading={convsLoading}
              convs={convs}
              failed={!convsLoading && convsError}
              onNavigateAgent={() => navigate('agent')}
              onOpenConversation={(id) => {
                // Hand off the selected conversation id, then navigate.
                // Falsy/malformed id → just open Agent normally (no target).
                if (id) setAgentConvTarget(id);
                navigate('agent');
              }}
            />

          </div>
        </div>

        {/* ── right rail ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

          {/* agent panel */}
          <div
            className="panel"
            style={{
              padding: 'var(--s5)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--s3)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
              }}
            >
              <span className="eyebrow">OpenClaw</span>
              <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} />
            </div>

            <div
              onClick={() => navigate('agent')}
              style={{ cursor: 'pointer' }}
              title="Open Local Agent"
            >
              <AgentSphere
                state={agentState}
                size={150}
                variant="orb"
                count={agentState === 'batch' ? 6 : undefined}
              />
            </div>

            <div style={{ textAlign: 'center' }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: meta?.tone === 'live' ? 'var(--live)' :
                         meta?.tone === 'amber' ? 'var(--amber)' :
                         meta?.tone === 'red' ? 'var(--red)' :
                         meta?.tone === 'violet' ? 'var(--violet)' :
                         meta?.tone === 'green' ? 'var(--green)' :
                         'var(--grey)',
                }}
              >
                {meta?.label ?? agentState}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--txt-2)' }}>{meta?.blurb}</div>
            </div>

            <form
              onSubmit={submitAsk}
              style={{ width: '100%', display: 'flex', gap: 6, marginTop: 4 }}
            >
              <input
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
                placeholder="Ask the agent…"
                style={{
                  flex: 1,
                  background: 'var(--surface-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 'var(--r2)',
                  padding: '8px 11px',
                  color: 'var(--txt-0)',
                  fontSize: 13,
                  fontFamily: 'var(--font-ui)',
                  outline: 'none',
                }}
              />
              <button className="btn btn-primary" type="submit" style={{ padding: '0 11px' }}>
                <Icon name="enter" size={15} />
              </button>
            </form>
          </div>

          {/* entity counts — real data */}
          <div className="panel panel-pad">
            <PanelHeader icon="cube" title="Entities" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--s2)', marginTop: 6 }}>
              {(
                [
                  { label: 'Projects',   value: summary?.entities.projects,   nav: 'projects'   as RouteId },
                  { label: 'Courses',    value: summary?.entities.courses,     nav: 'courses'    as RouteId },
                  { label: 'Hackathons', value: summary?.entities.hackathons,  nav: 'hackathons' as RouteId },
                  { label: 'Business',   value: summary?.entities.business,    nav: 'business'   as RouteId },
                ] as const
              ).map((e) => (
                <button
                  key={e.label}
                  className="btn"
                  style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2, padding: '8px 10px' }}
                  onClick={() => navigate(e.nav)}
                >
                  <span style={{ fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', lineHeight: 1, color: 'var(--txt-0)' }}>
                    {summaryLoading ? '…' : (e.value ?? '?')}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--txt-2)' }}>{e.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* runtime status */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="shield"
              title="Runtime status"
              right={
                <button className="btn btn-sm btn-ghost" onClick={() => navigate('safety')}>
                  <Icon name="chevron" size={13} />
                </button>
              }
            />
            {/* real: backend, brain CLI, vault, local model — live backend/API data */}
            <SystemRow service={backendService} />
            <SystemRow service={brainService} />
            <SystemRow service={vaultService} />
            <SystemRow service={localModelService} />
            {/* planned PRD runtimes — not implemented in this build */}
            <div style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--txt-3)',
              marginTop: 'var(--s3)',
              paddingTop: 'var(--s2)',
              borderTop: '1px solid var(--line-soft)',
            }}>
              Planned — not wired yet
            </div>
            {[SYSTEM.openclaw, SYSTEM.nemoclaw, SYSTEM.browser, SYSTEM.computer, SYSTEM.mcp].map(
              (svc, i) => <SystemRow key={i} service={svc} />
            )}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                marginTop: 'var(--s3)',
                color: 'var(--txt-2)',
              }}
            >
              <Icon name="folder" size={13} />
              <span
                className="mono"
                style={{
                  fontSize: 10.5,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {vaultDisplay}
              </span>
            </div>
          </div>

          {/* quick actions */}
          <div className="panel panel-pad">
            <PanelHeader
              icon="bolt"
              title="Quick actions"
              right={<span className="kbd">⌘K</span>}
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 'var(--s2)',
              }}
            >
              {QUICK_ACTIONS.slice(0, 8).map((q) => (
                <button
                  key={q.id}
                  className="btn"
                  style={{ justifyContent: 'flex-start', fontSize: 12 }}
                  onClick={() => runCommand(q.id)}
                >
                  <Icon name={q.glyph} size={14} />
                  {q.label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
