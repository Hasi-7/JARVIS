# Brain UI

Local-first personal AI command center. React + Vite + TypeScript + Tailwind CSS.

## Setup

```bash
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build → dist/
npm run preview  # preview production build locally
```

## What's built

**App shell**
- Sidebar with grouped nav (Operate / Intake / Work / Control), live badges, vault-synced footer
- Top command bar: screen title · ⌘K palette trigger · runtime status pills · agent mode dropdown
- `⌘K` / `Ctrl+K` command palette with fuzzy search over nav + quick actions + brain commands

**Dashboard** (hi-fi)
- Header: date, focus line, quick actions (Run today / Weekly / Upload raw)
- Count strip: 6 clickable metric tiles (Approvals · Raw pending · Escalations · Calendar · Backfill · Resume)
- Main column: Today's plan, Pending approvals (batch), 2-up (command output + recent AI work)
- Right rail: Agent panel (sphere + mode + ask input), Runtime status, Quick actions grid
- Clicking the sphere navigates to Local Agent

**AgentSphere** — all 13 states from DESIGN.md
`idle · listening · thinking · speaking · researching · browser · computeruse · pending · batch · escalation · blocked · guarded · locked`
AgentSphere is read-only in all product UI. Its state is driven by `agentState` in the Zustand store (currently mock-driven; will be wired to the backend status endpoint). The Local Agent cockpit page includes a state scrubber for development/testing.

**Stub pages** — all 15 routes beyond Dashboard
`agent · research · inbox · consolidate · calendar · tasks · projects · hackathons · courses · business · resume · backfill · escalation · safety · settings`

Agent and Inbox pages are semi-structured. Settings shows path config and build info only.

## Design decisions (fixed)

- **Accent**: Azure (`--accent-h: 218`, oklch). Not user-selectable — fixed for this product.
- **Sphere style**: Orb (`variant="orb"`). Not user-selectable — fixed for this product.
- **Visual customization is intentionally not exposed** in the current UI. The design system is opinionated and stable; the Tweaks panel from the prototype is not included.

## Runtime values (mocked)

All runtime values are currently mocked in `src/data/mock.ts`. The canonical single source is `APP_CONFIG`:

```ts
export const APP_CONFIG = {
  vaultPath: 'D:\\Hasnain\\Obsidian\\AI-Command-Center',
  brainCmd:  'D:\\Hasnain\\Personal\\bin\\brain.cmd',
}
```

`SYSTEM` reads from `APP_CONFIG` — nothing else should hardcode these paths.

Real values will come from backend endpoints once the FastAPI layer is built:
- `vault path` → `brain vault-path` CLI call
- `brain.cmd`  → backend config endpoint

## Stack

| Layer | Choice |
|---|---|
| Build | Vite 5 |
| UI framework | React 18 + TypeScript |
| Styling | Tailwind CSS v3 + CSS custom properties (oklch design tokens) |
| State | Zustand |
| Fonts | Schibsted Grotesk (UI) · JetBrains Mono (machine data) via Google Fonts |

## File structure

```
src/
  types/index.ts          shared TypeScript types
  data/mock.ts            typed mock data — APP_CONFIG is the single source for paths
  lib/utils.ts            tone helpers (toneVar, toneBg, toneLine)
  store/useAppStore.ts    Zustand store (route, agentState, agentMode, palette, toast)
  index.css               design tokens (--bg-0…--line-strong, --live, --amber…) + keyframes
  components/
    ui/                   Icon · AgentSphere · StatusDot · Pill · RiskBadge · ConfidenceBadge
                          PanelHeader · TagChip · SourceGlyph · ModeBadge · CommandPalette · EmptyState
    dashboard/            StatusCard · PlanBlock · ApprovalRow · SystemRow
    layout/               AppShell · Sidebar · TopCommandBar
  pages/                  DashboardPage + 15 stubs
  App.tsx                 route switch
  main.tsx                entry point
```

## What's NOT implemented yet

- Real OpenClaw / NemoClaw / brain CLI calls
- FastAPI backend
- File upload / classification
- Real research runs
- Calendar export
- Vault read/write
- Gmail / MCP
- Browser harness / computer use
