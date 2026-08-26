/**
 * Browser / Computer Use — PRD §15 nav item 5, §13, MVP v7.
 *
 * This section was missing entirely: computer-use had four working endpoints and
 * the only UI was an app-wide banner showing status and a Stop button, so a
 * session could not be scoped or started from the app at all, and the per-session
 * action log had nowhere to appear.
 *
 * Starting a session is deliberately a *request*, not an action. It queues a
 * `computer.start_session` approval that the operator approves and executes from
 * the queue below — that queue is what enforces Assist mode.
 */
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import type { ComputerUseStatusResponse, ToolConnectionStatus } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';
import { PanelHeader } from '@/components/ui/PanelHeader';
import { EmptyState } from '@/components/ui/EmptyState';
import { ToolApprovalQueue } from '@/components/tools/ToolApprovalQueue';
import { PermissionLogPanel } from '@/components/tools/PermissionLogPanel';
import { useRuntimeStatus } from '@/lib/runtimeStatus';
import { useAppStore } from '@/store/useAppStore';

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--surface-3)', color: 'var(--txt-0)',
  border: '1px solid var(--line)', borderRadius: 'var(--r2)',
  font: 'inherit', fontSize: 12, padding: '7px 9px',
};

function SessionScopeForm({ onQueued }: { onQueued: () => void }) {
  const showToast = useAppStore((s) => s.showToast);
  const [task, setTask] = useState('');
  const [windows, setWindows] = useState('');
  const [budget, setBudget] = useState('300');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allowedWindows = windows.split('\n').map((w) => w.trim()).filter(Boolean);
  const canSubmit = task.trim().length > 0 && allowedWindows.length > 0 && token.length > 0 && !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const parsedBudget = Number.parseInt(budget, 10);
      await api.requestComputerUseSession({
        task: task.trim(),
        allowedWindows,
        budgetSeconds: Number.isFinite(parsedBudget) ? parsedBudget : undefined,
      }, token);
      showToast('Session queued for approval. Approve and execute it below.');
      setTask('');
      setWindows('');
      onQueued();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Request failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel panel-pad" onSubmit={submit}>
      <PanelHeader icon="grid" title="Request a session" sub="scope now · approve below · then it can act" />

      <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5, marginBottom: 'var(--s3)' }}>
        A session authorises real clicks and keystrokes on the windows you list, for the
        budget you set. Before every action the foreground window is re-checked against
        this list — if focus has moved, the action is <strong>refused, never retargeted</strong>.
      </div>

      <label style={{ display: 'block', fontSize: 10.5, color: 'var(--txt-2)', marginBottom: 'var(--s3)' }}>
        Scoped task
        <input
          value={task} maxLength={300} onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. File the screenshots in the Obsidian attachments folder"
          style={{ ...inputStyle, marginTop: 4 }} disabled={busy}
        />
      </label>

      <label style={{ display: 'block', fontSize: 10.5, color: 'var(--txt-2)', marginBottom: 'var(--s3)' }}>
        Allowed windows — one title fragment per line
        <textarea
          value={windows} rows={3} onChange={(e) => setWindows(e.target.value)}
          placeholder={'Obsidian\nExplorer'}
          style={{ ...inputStyle, marginTop: 4, resize: 'vertical' }} disabled={busy}
        />
        <span style={{ color: 'var(--txt-3)' }}>
          {allowedWindows.length === 0
            ? 'Required. An empty list would permit acting on any window.'
            : `${allowedWindows.length} window${allowedWindows.length === 1 ? '' : 's'} allowed`}
        </span>
      </label>

      <div style={{ display: 'flex', gap: 'var(--s3)', marginBottom: 'var(--s3)' }}>
        <label style={{ flex: '0 0 130px', fontSize: 10.5, color: 'var(--txt-2)' }}>
          Budget (seconds)
          <input
            value={budget} inputMode="numeric" onChange={(e) => setBudget(e.target.value)}
            style={{ ...inputStyle, marginTop: 4 }} disabled={busy}
          />
        </label>
        <label style={{ flex: 1, fontSize: 10.5, color: 'var(--txt-2)' }}>
          Operator token
          <input
            type="password" value={token} onChange={(e) => setToken(e.target.value)}
            placeholder="X-Brain-Approval-Token"
            style={{ ...inputStyle, marginTop: 4 }} disabled={busy}
          />
        </label>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 11.5, marginBottom: 'var(--s3)' }}>
          <StatusDot tone="red" /><span style={{ flex: 1 }}>{error}</span>
        </div>
      )}

      <button type="submit" className="btn btn-sm btn-primary" disabled={!canSubmit}>
        {busy ? 'Queueing…' : 'Queue session for approval'}
      </button>
      <div style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 6, lineHeight: 1.45 }}>
        This queues an approval. It does not start a session or perform any input.
      </div>
    </form>
  );
}

function ActiveSession({ status, onStopped }: {
  status: ComputerUseStatusResponse;
  onStopped: () => void;
}) {
  const showToast = useAppStore((s) => s.showToast);
  const [stopping, setStopping] = useState(false);
  const session = status.active;

  if (!session) {
    return (
      <div className="panel panel-pad">
        <PanelHeader icon="grid" title="Active session" sub="none" />
        <div style={{ fontSize: 12, color: 'var(--txt-2)', lineHeight: 1.5 }}>
          {status.enabled
            ? 'No session is running. Nothing can click or type on your desktop right now.'
            : 'Computer-use is off. The kill switch (BRAIN_UI_COMPUTER_USE_ENABLED) is not set, so no session can start at all.'}
        </div>
      </div>
    );
  }

  async function stop() {
    setStopping(true);
    try {
      await api.stopComputerUseSession(session!.id!);
      showToast('Session stopped.');
      onStopped();
    } catch {
      showToast('Could not stop the session — check the backend.');
    } finally {
      setStopping(false);
    }
  }

  return (
    <div className="panel panel-pad" style={{ borderColor: 'var(--red-line)' }}>
      <PanelHeader icon="grid" title="Active session" sub="this can act on your desktop" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', marginBottom: 'var(--s3)' }}>
        <StatusDot tone="red" pulse />
        <span style={{ flex: 1, fontSize: 12.5, color: 'var(--txt-0)' }}>{session.task}</span>
        <button className="btn btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red-line)' }}
                onClick={stop} disabled={stopping}>
          {stopping ? 'Stopping…' : 'Stop now'}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '110px minmax(0,1fr)', gap: '5px 10px', fontSize: 11.5 }}>
        <span style={{ color: 'var(--txt-3)' }}>Allowed windows</span>
        <span className="mono">{session.allowedWindows.join(' · ')}</span>
        <span style={{ color: 'var(--txt-3)' }}>Time left</span>
        <span className="mono">{Math.max(0, Math.round(session.remainingSeconds))}s of {session.budgetSeconds}s</span>
        <span style={{ color: 'var(--txt-3)' }}>Actions</span>
        <span className="mono">
          {session.actionCount}
          {session.refusedCount > 0 && (
            <span style={{ color: 'var(--red)' }}> · {session.refusedCount} refused</span>
          )}
        </span>
      </div>
    </div>
  );
}

export function ComputerUsePage() {
  const [status, setStatus] = useState<ComputerUseStatusResponse | null>(null);
  const [tools, setTools] = useState<ToolConnectionStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const runtime = useRuntimeStatus();

  const load = useCallback(async () => {
    setError(null);
    const [cu, tl] = await Promise.allSettled([
      api.computerUseStatus(),
      api.getToolConnectionStatus(),
    ]);
    if (cu.status === 'fulfilled') setStatus(cu.value);
    else setError(cu.reason instanceof Error ? cu.reason.message : 'Failed to read computer-use status.');
    if (tl.status === 'fulfilled') setTools(tl.value.items);
  }, []);

  useEffect(() => { load(); }, [load, refresh]);
  useEffect(() => {
    // A session is time-boxed and can end on its own, so poll while the page is open.
    const timer = window.setInterval(load, 5_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const browser = (tools ?? []).find((t) => t.id === 'browser-harness');
  const sandbox = runtime.items.find((i) => i.id === 'nemoclaw_openshell');

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 'var(--s5)' }}>

      <div>
        <div style={{ fontSize: 18, fontWeight: 700 }}>Browser / Computer Use</div>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-3)', marginTop: 3 }}>
          sandboxed browsing · supervised desktop control
        </div>
      </div>

      {/* the standing warning */}
      <div style={{ padding: 'var(--s3) var(--s4)', background: 'var(--surface-2)', border: '1px solid var(--red-line)', borderRadius: 'var(--r2)', fontSize: 12, color: 'var(--txt-1)', display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: 1.5 }}>
        <Icon name="shield" size={14} style={{ color: 'var(--red)', marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>Computer-use controls your real desktop.</strong> There is no sandbox around
          host input, so the guards are the safety: a scoped session with a window allowlist,
          a foreground check before every action, per-action confirmation for risky categories,
          a wall-clock budget, and outright refusal to type into a credential window. Every
          action and refusal is written to the audit log.
        </span>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)', background: 'var(--red-bg)', border: '1px solid var(--red-line)', fontSize: 12 }}>
          <StatusDot tone="red" /><span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={load}>Retry</button>
        </div>
      )}

      {status && <ActiveSession status={status} onStopped={() => setRefresh((n) => n + 1)} />}

      {status?.enabled
        ? <SessionScopeForm onQueued={() => setRefresh((n) => n + 1)} />
        : (
          <EmptyState
            icon="shield"
            title="Computer-use is off"
            desc="Start the backend with BRAIN_UI_COMPUTER_USE_ENABLED=true and an operator token set. It is off by default and should stay off unless you are actively using it."
          />
        )}

      {/* browser harness */}
      <div className="panel panel-pad">
        <PanelHeader icon="search" title="Browser harness" sub="sandboxed page reads and search" />
        <div style={{ fontSize: 11.5, color: 'var(--txt-1)', lineHeight: 1.5 }}>
          Browsing runs from a time-boxed <strong>research session</strong> on the Research page.
          Every fetch executes inside the OpenShell sandbox, against that session's domain
          allowlist, and fails closed if the sandbox is unhealthy or its policy would not
          actually enforce isolation.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '150px minmax(0,1fr)', gap: '5px 10px', fontSize: 11.5, marginTop: 'var(--s3)' }}>
          <span style={{ color: 'var(--txt-3)' }}>Harness status</span>
          <span>{browser ? browser.status.replace(/_/g, ' ') : '—'}</span>
          <span style={{ color: 'var(--txt-3)' }}>Sandbox runtime</span>
          <span>{sandbox ? sandbox.status.replace(/_/g, ' ') : '—'}</span>
        </div>
      </div>

      {/* the approval queue that gates all of this */}
      <ToolApprovalQueue onChanged={() => setRefresh((n) => n + 1)} />

      {/* per-session action log, filtered to computer-use */}
      <PermissionLogPanel
        limit={25}
        refreshSignal={refresh}
        description={
          <>
            Every computer-use action and every refusal is recorded here and mirrored to{' '}
            <span className="mono" style={{ fontSize: 11 }}>ops/tool-logs/</span> in the vault.
            Typed text is never logged — only its length.
          </>
        }
      />

    </div>
  );
}
