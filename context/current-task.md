# Current Task

## Goal

Build the first frontend foundation for Brain UI in the new repo.

This task is only the initial UI shell and Dashboard v0. It should establish the visual system, layout, mock state, and component structure from `DESIGN.md` while staying consistent with `PRD_NemoClaw_OpenShell.md`.

The goal is to create a clean React/Vite/TypeScript frontend foundation that can later connect to the real backend, OpenClaw, NemoClaw/OpenShell, `brain` CLI, MCP gateway, browser harness, computer use, and Obsidian vault.

## Relevant Files

Use these files as the source of truth:

* `PRD_NemoClaw_OpenShell.md`
* `DESIGN.md`
* Claude Design mockup files, if provided

Source-of-truth order:

1. `PRD_NemoClaw_OpenShell.md` controls product requirements, architecture, agent responsibilities, safety model, and long-term scope.
2. `DESIGN.md` controls UI/UX, layout, visual style, navigation, components, tokens, and interaction behavior.
3. Mockup files are visual references only.
4. This task file controls implementation scope for this run.

If there is a conflict, follow the PRD and `DESIGN.md`.

## Constraints

Use:

* React
* Vite
* TypeScript
* Tailwind CSS
* shadcn/ui where useful
* CSS variables for design tokens
* Typed mock data

Implement:

* App shell
* Sidebar navigation
* Top command bar
* Command palette shell
* Dashboard v0
* AgentSphere component with mocked states
* Runtime status UI for OpenClaw, NemoClaw/OpenShell, Browser, Computer Use, MCP gateway, and vault path
* Stub pages for non-Dashboard routes
* README setup/run instructions

The app should feel like a restrained, Jarvis-inspired local-first command center: serious, calm, dense, technical, and useful.

Use the design principles from `DESIGN.md`:

* Friction-calibrated
* Real state only
* Calm density

## Do Not Touch

Do not implement real privileged or backend behavior in this run.

Do not build:

* real backend
* FastAPI
* real `brain` command execution
* real OpenClaw calls
* real NemoClaw/OpenShell integration
* MCP gateway
* Gmail integration
* Obsidian read/write logic
* real file upload or routing
* browser harness
* computer use
* real research agent
* real Claude Code/OpenCode launch
* real calendar export
* real vault mutation

Do not blindly copy prototype architecture from Claude Design mockups.

Mockup files may be used for visual reference only. Do not preserve CDN/Babel setup, one-file architecture, prototype hacks, or mock logic as production architecture.

## Acceptance Criteria

This task is complete when:

* The app launches locally with Vite.
* The app has a clean desktop-first shell with sidebar, top bar, and main content.
* Sidebar nav matches the grouped structure in `DESIGN.md`.
* Top bar includes command palette trigger, runtime status pills, and agent mode dropdown.
* Command palette opens and supports mock navigation/actions.
* Dashboard v0 includes:

  * header/focus line
  * quick actions
  * metric/count strip
  * today’s plan
  * pending approvals
  * recent command output
  * recent AI work
  * agent panel
  * runtime status panel
  * quick actions grid
* `AgentSphere` supports the required states from `DESIGN.md`.
* Runtime status UI includes OpenClaw, NemoClaw/OpenShell, Browser, Computer Use, MCP gateway, and vault path.
* Non-Dashboard pages have clean stub pages.
* Mock data is typed and isolated.
* Styling follows `DESIGN.md`: graphite surfaces, restrained accents, mono only for technical data, no excessive glow.
* No real privileged actions are implemented.
* README explains how to install and run the app.

## Test Plan

Run:

```bash
npm install
npm run dev
```

Then verify:

* App loads without runtime errors.
* Dashboard is the default route.
* Sidebar navigation works.
* Stub pages render for non-Dashboard routes.
* Command palette opens by click and keyboard shortcut if implemented.
* Mock commands update command output, show a toast, or visibly perform a safe mock action.
* Agent mode dropdown works with mock state.
* AgentSphere visually changes when its mocked state changes.
* Runtime status panel displays all required systems.
* Layout remains usable on a normal desktop/laptop width.
* TypeScript check passes if configured.
* Build passes:

```bash
npm run build
```

## Open Questions

* Should routing use React Router now, or simple local state until the backend is added?
* Should shadcn/ui be fully installed in this first run, or only added when components need it?
* Which exact font stack should be used if external fonts are avoided?
* Should mock state be stored in plain TypeScript files, Zustand, or simple React state for now?
* Should the next run add the backend skeleton first or finish the Local Agent and Raw Inbox UI screens first?
