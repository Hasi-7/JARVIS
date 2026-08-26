import { useAppStore } from '@/store/useAppStore';
import { AppShell } from '@/components/layout/AppShell';
import { DashboardPage }   from '@/pages/DashboardPage';
import { AgentPage }       from '@/pages/AgentPage';
import { ResearchPage }    from '@/pages/ResearchPage';
import { InboxPage }       from '@/pages/InboxPage';
import { ConsolidatePage } from '@/pages/ConsolidatePage';
import { EmailIntakePage } from '@/pages/EmailIntakePage';
import { CalendarPage }    from '@/pages/CalendarPage';
import { TasksPage }       from '@/pages/TasksPage';
import { ProposalsPage }   from '@/pages/ProposalsPage';
import { ProjectsPage }    from '@/pages/ProjectsPage';
import { HackathonsPage }  from '@/pages/HackathonsPage';
import { CoursesPage }     from '@/pages/CoursesPage';
import { BusinessPage }    from '@/pages/BusinessPage';
import { ResumePage }      from '@/pages/ResumePage';
import { BackfillPage }    from '@/pages/BackfillPage';
import { EscalationPage }  from '@/pages/EscalationPage';
import { ComputerUsePage } from '@/pages/ComputerUsePage';
import { ToolConnectionsPage } from '@/pages/ToolConnectionsPage';
import { SafetyPage }      from '@/pages/SafetyPage';
import { SettingsPage }    from '@/pages/SettingsPage';

function Screen() {
  const route = useAppStore((s) => s.route);
  switch (route) {
    case 'dashboard':   return <DashboardPage />;
    case 'agent':       return <AgentPage />;
    case 'research':    return <ResearchPage />;
    case 'inbox':       return <InboxPage />;
    case 'consolidate': return <ConsolidatePage />;
    case 'email':       return <EmailIntakePage />;
    case 'calendar':    return <CalendarPage />;
    case 'tasks':       return <TasksPage />;
    case 'proposals':   return <ProposalsPage />;
    case 'projects':    return <ProjectsPage />;
    case 'hackathons':  return <HackathonsPage />;
    case 'courses':     return <CoursesPage />;
    case 'business':    return <BusinessPage />;
    case 'resume':      return <ResumePage />;
    case 'backfill':    return <BackfillPage />;
    case 'computeruse': return <ComputerUsePage />;
    case 'escalation':  return <EscalationPage />;
    case 'tools':       return <ToolConnectionsPage />;
    case 'safety':      return <SafetyPage />;
    case 'settings':    return <SettingsPage />;
    default:            return <DashboardPage />;
  }
}

export default function App() {
  return (
    <AppShell>
      <Screen />
    </AppShell>
  );
}
