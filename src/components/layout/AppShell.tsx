import { useEffect } from 'react';
import type { RouteId } from '@/types';
import { useAppStore } from '@/store/useAppStore';
import { Sidebar } from './Sidebar';
import { TopCommandBar } from './TopCommandBar';
import { CommandPalette } from '@/components/ui/CommandPalette';
import { Icon } from '@/components/ui/Icon';
import { ComputerUseBanner } from '@/components/ui/ComputerUseBanner';
import { resolveQuickAction } from '@/lib/quickActions';
import { resolveAgentState } from '@/lib/agentSphereState';
import { api } from '@/lib/api';
import { toBackendMode } from '@/lib/agentModes';
import type { EntityKind } from '@/store/useAppStore';

const ENTITY_ROUTE: Record<EntityKind, RouteId> = {
  project: 'projects', course: 'courses', hackathon: 'hackathons', business: 'business',
};

interface AppShellProps {
  children: React.ReactNode;
  scrollable?: boolean;
}

export function AppShell({ children, scrollable = true }: AppShellProps) {
  const route            = useAppStore((s) => s.route);
  const navigate         = useAppStore((s) => s.navigate);
  const paletteOpen      = useAppStore((s) => s.paletteOpen);
  const openPalette      = useAppStore((s) => s.openPalette);
  const closePalette     = useAppStore((s) => s.closePalette);
  const toast            = useAppStore((s) => s.toast);
  const showToast        = useAppStore((s) => s.showToast);
  const checkBackend     = useAppStore((s) => s.checkBackend);
  const runBrainCommand  = useAppStore((s) => s.runBrainCommand);
  const loadStagedCount  = useAppStore((s) => s.loadStagedCount);
  const loadAgentModes   = useAppStore((s) => s.loadAgentModes);
  const setEntityCreateTarget = useAppStore((s) => s.setEntityCreateTarget);
  const setAgentState    = useAppStore((s) => s.setAgentState);
  const agentMode        = useAppStore((s) => s.agentMode);
  const pendingProposals = useAppStore((s) => s.pendingProposalCount);

  // Check backend availability, load staged count, and load agent mode policy once on mount
  useEffect(() => {
    checkBackend();
    loadStagedCount();
    loadAgentModes();
  }, [checkBackend, loadStagedCount, loadAgentModes]);

  /**
   * Drive the sphere from real system state.
   *
   * Deliberately does NOT touch the transient chat states (thinking/speaking/
   * blocked), which AgentPage owns for the duration of a turn — overwriting
   * those from a poll would make the sphere flicker mid-response. This only
   * fills in the ambient states that nothing was setting at all.
   */
  useEffect(() => {
    let alive = true;
    const TRANSIENT = new Set(['thinking', 'speaking', 'blocked', 'listening']);

    const sync = async () => {
      const [cu, research] = await Promise.allSettled([
        api.computerUseStatus(),
        api.listResearchSessions(),
      ]);
      if (!alive) return;
      // A chat turn in flight always wins; leave it alone.
      if (TRANSIENT.has(useAppStore.getState().agentState)) return;

      const computerUseActive = cu.status === 'fulfilled' && cu.value.active != null;
      const activeResearch = research.status === 'fulfilled'
        ? research.value.sessions.find((s) => s.status === 'active')
        : undefined;

      setAgentState(resolveAgentState({
        computerUseActive,
        researchActive: activeResearch != null,
        pendingApprovals: pendingProposals,
        mode: toBackendMode(agentMode.id),
      }));
    };

    sync();
    const timer = window.setInterval(sync, 10_000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [setAgentState, agentMode, pendingProposals]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        paletteOpen ? closePalette() : openPalette();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [paletteOpen, openPalette, closePalette]);

  const handleCommand = (id: string) => {
    const resolved = resolveQuickAction(id);
    switch (resolved.kind) {
      case 'navigate':
        navigate(resolved.route);
        return;
      case 'brain':
        runBrainCommand(resolved.command);
        return;
      case 'entity':
        // The creation modals live on the entity pages; go there and open it.
        navigate(ENTITY_ROUTE[resolved.entity]);
        setEntityCreateTarget(resolved.entity);
        return;
      default:
        showToast(`Unknown action: ${resolved.id}`);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar route={route} onNavigate={(r: RouteId) => navigate(r)} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Above everything: a live computer-use session must be impossible to
            miss from any page, with Stop always one click away (PRD §13.3). */}
        <ComputerUseBanner />
        <TopCommandBar route={route} />
        <main
          style={{
            flex: 1,
            overflowY: scrollable ? 'auto' : 'hidden',
            padding: 'var(--s6)',
            minHeight: 0,
          }}
        >
          {children}
        </main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={closePalette}
        onNavigate={(r: RouteId) => navigate(r)}
        onCommand={handleCommand}
      />

      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 300,
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            padding: '10px 16px',
            background: 'var(--surface-2)',
            border: '1px solid var(--live-line)',
            borderRadius: 'var(--r-pill)',
            boxShadow: 'var(--shadow-2)',
            fontSize: 13,
            color: 'var(--txt-0)',
            whiteSpace: 'nowrap',
          }}
        >
          <Icon name="check" size={15} style={{ color: 'var(--live)' }} />
          {toast}
        </div>
      )}
    </div>
  );
}
