import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ComputerUseStatusResponse } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';

/**
 * Visible computer-use session indicator (PRD §13.3: "no hidden background
 * operation", "user interrupt/stop button").
 *
 * Mounted app-wide so a live session is impossible to miss from any page, and
 * Stop is always one click away. Both the status read and the stop call are
 * deliberately unauthenticated on the backend, so this renders and can halt a
 * session even if the operator token is not to hand.
 */

const POLL_MS = 2000;

export function ComputerUseBanner() {
  const [status, setStatus] = useState<ComputerUseStatusResponse | null>(null);
  const [stopping, setStopping] = useState(false);

  const poll = useCallback(async () => {
    try {
      setStatus(await api.computerUseStatus());
    } catch {
      setStatus(null);      // backend down — show nothing rather than a stale claim
    }
  }, []);

  useEffect(() => {
    void poll();
    const timer = window.setInterval(poll, POLL_MS);
    return () => window.clearInterval(timer);
  }, [poll]);

  const active = status?.active;
  if (!active) return null;

  const stop = async () => {
    if (!active.id) return;
    setStopping(true);
    try {
      await api.stopComputerUseSession(active.id);
      await poll();
    } finally {
      setStopping(false);
    }
  };

  const remaining = Math.max(0, Math.round(active.remainingSeconds));

  return (
    <div
      role="status"
      aria-live="assertive"
      style={{
        position: 'sticky', top: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', gap: 'var(--s3)',
        padding: 'var(--s3) var(--s5)',
        background: 'var(--red-bg)',
        borderBottom: '2px solid var(--red-line)',
        color: 'var(--txt-0)',
      }}
    >
      <span
        style={{
          width: 10, height: 10, borderRadius: '50%', background: 'var(--red)',
          flexShrink: 0, animation: 'pulse 1.2s ease-in-out infinite',
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700 }}>
          Computer-use session active — this can act on your desktop
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-1)', marginTop: 2 }}>
          {active.task} · {remaining}s left · {active.actionCount} action
          {active.actionCount === 1 ? '' : 's'}
          {active.refusedCount > 0 && ` · ${active.refusedCount} refused`}
          {' · '}windows: {active.allowedWindows.join(', ')}
        </div>
      </div>
      <button
        className="btn btn-sm"
        onClick={stop}
        disabled={stopping}
        style={{ background: 'var(--red)', color: '#fff', borderColor: 'var(--red)', fontWeight: 600 }}
      >
        <Icon name="x" size={13} />
        {stopping ? 'Stopping…' : 'Stop now'}
      </button>
    </div>
  );
}
