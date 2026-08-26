/**
 * Hackathons — PRD §21.
 *
 * §21 asks for date, team, theme, result/placement, repo, GitHub, demo and
 * submission links. Those now live in the note's YAML frontmatter and render on
 * the card, so the archive is a real record rather than a folder listing.
 */
import { useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api } from '@/lib/api';
import type { VaultHackathon } from '@/lib/api';
import { EntityListPage } from '@/components/entities/EntityListPage';
import type { EntityAction } from '@/components/entities/EntityCard';

export function HackathonsPage() {
  const navigate = useAppStore((s) => s.navigate);
  const runBrainCommand = useAppStore((s) => s.runBrainCommand);

  const load = useCallback(
    async () => (await api.getVaultHackathons()).hackathons,
    [],
  );

  const actionsFor = useCallback((item: VaultHackathon): EntityAction[] => [
    {
      label: 'Archive',
      title: 'Runs `brain archive-hackathon` for this hackathon',
      onClick: () => runBrainCommand('archive-hackathon', { name: item.name }),
    },
    { label: 'Upload source', title: 'Route submission material from the Raw Inbox', onClick: () => navigate('inbox') },
    { label: 'Consolidate', title: 'Bring AI chat work into the vault', onClick: () => navigate('consolidate') },
    { label: 'Resume row', title: 'Track this as resume evidence', onClick: () => navigate('resume') },
  ], [navigate, runBrainCommand]);

  return (
    <EntityListPage<VaultHackathon>
      title="Hackathons"
      kind="hackathon"
      pathHint="wiki/projects/hackathons/ · raw/hackathons/"
      icon="flag"
      newLabel="New Hackathon"
      emptyTitle="No hackathons found"
      emptyDesc="No .md files in wiki/projects/hackathons/ and no folders in raw/hackathons/. Create one or route hackathon files from the Raw Inbox."
      safetyNote={
        <>
          Archive runs the allowlisted <span className="mono">brain archive-hackathon</span>.
          Record date, team, theme, result and the Devpost link in the note's frontmatter —
          <span className="mono"> demo_url</span> holds the submission link.
        </>
      }
      load={load}
      actionsFor={actionsFor}
      create={{
        note: "Creates the hackathon using `brain new-hackathon <name>`. Add date, team, theme, result and links to the note's frontmatter afterwards.",
        fields: [{ key: 'name', label: 'Name', placeholder: 'Hackathon name', required: true }],
        submit: (values) => api.createHackathon({ name: values.name.trim() }),
      }}
    />
  );
}
