import { useEffect } from 'react';
import type { RouteId } from '@/types';
import { useAppStore } from '@/store/useAppStore';
import { Sidebar } from './Sidebar';
import { TopCommandBar } from './TopCommandBar';
import { CommandPalette } from '@/components/ui/CommandPalette';
import { Icon } from '@/components/ui/Icon';
import { QUICK_ACTIONS } from '@/data/mock';

// brain subcommands that can be executed via backend (mirrors backend allowlist subset)
const BRAIN_ACTION_MAP: Record<string, string> = {
  today:     'today',
  weekly:    'weekly',
  syncraw:   'sync-raw',
  calexport: 'calendar-export',
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

  // Check backend availability and load staged count once on mount
  useEffect(() => {
    checkBackend();
    loadStagedCount();
  }, [checkBackend, loadStagedCount]);

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
    if (id === 'ask')         { navigate('agent');       return; }
    if (id === 'research')    { navigate('research');    return; }
    if (id === 'consolidate') { navigate('consolidate'); return; }
    if (id === 'upload')      { navigate('inbox');       return; }
    const brainCmd = BRAIN_ACTION_MAP[id];
    if (brainCmd) {
      runBrainCommand(brainCmd);
      return;
    }
    const action = QUICK_ACTIONS.find((a) => a.id === id);
    if (action) showToast(action.cmd ? `${action.cmd} (not wired yet)` : `Opened ${action.label}`);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar route={route} onNavigate={(r: RouteId) => navigate(r)} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
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
