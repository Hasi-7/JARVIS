# Brain UI — Design Specification

> Restrained, Jarvis-inspired local-first command center for a personal AI workflow system.
> This document specifies the design as built in the `brain-ui/` prototype. It is the handoff
> reference for implementation (React + Vite + TS, Tailwind + shadcn/ui per the PRD).

---

## 1. Design philosophy

A capable **operating console**, not a SaaS dashboard and not a sci-fi screen. Three rules drive every decision:

1. **Friction-calibrated.** Safe, low-risk actions feel automatic. Medium-risk work is *batched* into preview/apply. High-risk work needs explicit confirmation. The UI never makes the user babysit the agent.
2. **Real state only.** Every animation, dot, ring, and badge maps to an actual backend state. No decorative "busy" theater.
3. **Calm density.** Dense, high-contrast data tables sit inside calm graphite chrome. Strong hierarchy, generous negative space around the things that matter.

Tone of voice in copy: terse, operator-grade, reassuring about safety without nagging
(e.g. *"Batched — review, don't babysit"*, *"low-risk runs automatically · risky actions ask first"*).

---

## 2. Information architecture

Sidebar nav, grouped into four bands. Badges show live counts.

| Group | Sections |
|-------|----------|
| **Operate** | Dashboard · Local Agent · Research |
| **Intake** | Raw Inbox `7` · AI Consolidation · Calendar `3` · Tasks |
| **Work** | Projects · Hackathons · Courses · Business · Resume Pipeline · Backfill |
| **Control** | Escalation Queue `3` · Tool Safety · Settings |

Hi-fi depth: **Dashboard, Local Agent, Raw Inbox.** Semi-built: Research, AI Consolidation, Escalation Queue, Tool Safety, Calendar. Structured stubs: Tasks, Projects, Hackathons, Courses, Business, Resume, Backfill, Settings.

**Global chrome**
- **Sidebar** (220px): brand mark = a minimal state-reflecting orb (always visible, never dominating), grouped nav, "Vault synced" footer.
- **Top command bar** (56px): screen title · centered **⌘K command-palette** trigger · runtime status pills (OpenClaw / NemoClaw / Browser / CompUse) · **Agent mode dropdown**.
- **⌘K Command Palette**: fuzzy search over *actions* + *go-to nav* + *brain commands*. Arrow keys + Enter. The primary way to drive the app.

---

## 3. Design tokens

All tokens are CSS custom properties (`theme.css`). Colors are authored in **oklch** so hue/temperature/density are tweakable at runtime.

### 3.1 Graphite surfaces
Driven by `--base-h` (temperature hue) and `--base-c` (chroma).

| Token | Role | Value (cool default) |
|-------|------|----------------------|
| `--bg-0` | app void | `oklch(0.155 c h)` |
| `--bg-1` | sidebar / chrome | `oklch(0.185 c h)` |
| `--surface` | panels / cards | `oklch(0.213 c h)` |
| `--surface-2` | raised within panel | `oklch(0.245 c h)` |
| `--surface-3` | hover / input | `oklch(0.285 c h)` |
| `--line-soft` / `--line` / `--line-strong` | hairlines | `0.255 / 0.30 / 0.38` |

### 3.2 Text hierarchy
`--txt-0` primary `0.96` · `--txt-1` secondary `0.80` · `--txt-2` muted/labels `0.635` · `--txt-3` faint/placeholder `0.50`.

### 3.3 Accent & semantic states
One **live** accent (driven by `--accent-h`, default azure 230) plus fixed risk semantics. Each ships a base, a `-bg` (≈12–14% alpha) and a `-line` (≈34–38% alpha).

| Token | Meaning | Hue |
|-------|---------|-----|
| `--live` | live agent / interactive / info | accent (cyan–indigo) |
| `--amber` | pending · approval · medium risk | 78 |
| `--red` | blocked · danger · high risk | 25 |
| `--violet` | escalation | 288 |
| `--green` | ok · guarded · success · low risk | 158 |
| `--grey` | locked · inert | neutral |

### 3.4 Spacing, radius, elevation
- **Spacing** `--s1…--s8` (4 → 44px), all multiplied by `--density` (1 comfortable / 0.86 compact). Dense table row `--row-h` 38px × density.
- **Radius** `--r1` 5 · `--r2` 8 · `--r3` 12 · `--r4` 16 · `--r-pill` 999.
- **Shadow** restrained: `--shadow-1` (hairline lift), `--shadow-2` (panel), `--shadow-pop` (palette/menu). **No glow on UI elements** — only the agent sphere may emit light.

### 3.5 Typography
- **UI:** Schibsted Grotesk (default) — clean grotesque. Alternates: Hanken Grotesk, Archivo.
- **Mono:** JetBrains Mono (paths, logs, counts, timestamps, code). Alternates: IBM Plex Mono, Space Mono.
- Body 14px / 1.45. `.eyebrow` = 11px uppercase 0.09em muted labels. Metric values 22px/600 −0.01em.

### 3.6 Motion
`--ease: cubic-bezier(.22,.61,.36,1)` · `--fast` 130ms · `--med` 240ms. Keyframes: `breathe`, `spin`. **Functional only.** Honors `prefers-reduced-motion`.

---

## 4. Agent sphere — state model

A **status surface**, not a hero toy. Sized modestly (30px brand mark → 64px cockpit head → 150px dashboard panel). Composed of: a radial-gradient core orb, a solid presence dot, and an SVG ring layer. Three style variants (Tweak): `orb` (default, soft core), `rings` (wireframe/technical), `minimal` (dot + single ring). Locked/blocked never animate.

| State | Tone | Behavior |
|-------|------|----------|
| **Idle** | live | dim, slow breathing core + faint dashed rotation |
| **Listening** | live | thin outer pulse ring |
| **Thinking** | live | fast rotating dashed inner ring + counter-rotating outer |
| **Speaking** | live | ripple ring + 5-bar waveform |
| **Researching** | live | orbiting dot + dashed ring |
| **Browser active** | live | orbit dot + latitude ellipse (globe) |
| **Computer use** | live | rotating segmented ring + cursor glyph |
| **Tool request pending** | amber | solid amber ring, gentle flash |
| **Batch approval** | amber | rotating segmented ring + **count badge** |
| **Escalation** | violet | rotating segmented ring (violet) |
| **Blocked** | red | small static ring + slash, no motion |
| **Guarded** | green | ring + shield + check (NemoClaw active) |
| **Locked** | grey | greyscale static, dim presence |

Rule: the sphere reflects state; it does not invent it. State is global and shared between Dashboard panel, cockpit head, and sidebar mark.

---

## 5. Progressive autonomy — agent modes

Surfaced as a **dropdown** (top bar + dashboard agent panel) and as a selectable rail on the Local Agent page. Each shows label + one-line description.

| Mode | What the agent may do |
|------|------------------------|
| **Manual** | You drive. Agent can be off. |
| **Observe** | Reads app state, answers questions. No tools run. |
| **Draft** | Generates proposals. Nothing applied. |
| **Assist** *(default)* | Runs low-risk tools. Batches medium-risk for approval. |
| **Research** | Time-boxed browser harness. Produces a research packet. |
| **Computer Use** | Operates approved UI flows. Visibly supervised. |
| **Locked** | All agent tools disabled. UI works manually. |

If NemoClaw/OpenShell is unavailable, privileged modes degrade: browser/computer-use disabled, privileged calls blocked or converted to manual instructions; Dashboard + manual `brain` commands keep working.

---

## 6. Risk & approval UX

| Risk | Treatment | Examples |
|------|-----------|----------|
| **Low** (green) | auto-run | read vault, `brain status`, web search in an approved run, draft notes |
| **Medium** (amber) | **batch preview/apply** | move files, write notes, add tasks/calendar rows, save research/chat summaries |
| **High** (red) | explicit confirmation | send email, real calendar writes, delete/move notes, non-allowlisted shell |
| **Disabled** | off unless intentionally enabled | arbitrary shell, credential access, payments |

**Batch approval row** shows: what changes · files affected · reason · `ConfidenceBadge` (1–3 bars) · `RiskBadge`. Actions: *Apply N safe* · *Review* · per-item edit/reject. The dashboard surfaces the queue compactly; the cockpit shows the full tool-request card routed *through NemoClaw → backend gateway*.

---

## 7. Component inventory

Built and reusable (`components.jsx`, `sphere.jsx`, `icons.jsx`):

- **Layout:** AppShell (sidebar + top bar + main), Sidebar, TopCommandBar, CommandPalette, Toast, PanelHeader, `.panel`.
- **Agent:** AgentSphere, ModeBadge (dropdown), ModeItem rail.
- **Status & data:** StatusCard (metric tile), StatusDot (flat, optional pulse), Pill, RiskBadge, ConfidenceBadge, TagChip (domain color), SourceGlyph (ChatGPT/Claude/OpenCode), SystemRow.
- **Domain panels:** PlanBlock, ApprovalRow, ToolRequest, ResearchRunPanel (mini + full), FileClassificationRow, ObsidianDestination field, Detail/override drawer, EscalationQueueTable, NemoClawStatusPanel, CalendarCandidateTable, EmptyState.
- **Controls:** `.btn` (+ `-primary`, `-ghost`, `-sm`), `.kbd`, inputs/textarea, checkbox (accent-colored).

Icon set: single-weight (1.6) 24-grid stroke glyphs, no decorative illustration.

---

## 8. Hi-fi screen specs

### 8.1 Dashboard — daily operating view
- **Header:** date + greeting, today's focus line, quick actions (Run today / Weekly / Upload raw).
- **Count strip** (6 tiles, clickable → section): Approvals, Raw pending, Escalations, Calendar, Backfill %, Resume.
- **Main column:** Today's plan (timeline blocks; "now" highlighted), Pending approvals (batched list + *Apply N safe*), two-up Recent command output (mono, exit-state dots) + Recent AI work (source glyphs).
- **Right rail:** Agent panel (sphere + mode dropdown + *Ask the agent* input that triggers real thinking→speaking), Runtime status (OpenClaw/NemoClaw/Browser/CompUse/MCP rows + vault path), Quick actions grid (`⌘K`).

### 8.2 Local Agent — cockpit
- **Left rail:** mode selector (all 7 modes), Current context (project/course/vault/model), Memory used (files).
- **Center:** cockpit head (sphere 64 + state label + *Disable tools*), **state strip** (scrub all sphere states), conversation transcript (user/agent bubbles, proposal chips, research-start marker), composer with action buttons (Create proposal / Research / Consolidate / Escalate) + textarea (Enter to send).
- **Right rail:** Tool-request approval card (appears in `pending`), live Research run (budget bar, sources, claims, confidence, **"Not yet checked"** gaps, Escalate / Save to vault).

### 8.3 Raw Inbox — frictionless intake
- **Dropzone:** real drag-drop, hover-lit; dropped files stage and run a **live classification animation** (progress shimmer → domain/destination/confidence).
- **Table:** checkbox · file (mono name + size) · domain TagChip · proposed destination (mono path) · ConfidenceBadge · status (Pending/Review). Batch bar: *Batch approve N high-conf* · *Sync raw*.
- **Detail/override drawer:** AI classification + reason, editable Domain/Entity/Source-type, proposed destination with edit, safety note ("original never deleted, never overwrite without confirmation"), actions Reject / Override / **Route file**.

### 8.4 Semi-built (structure complete)
Research (query + 6 time budgets + scope + depth + live progress + findings/gaps), AI Consolidation (source picker + extraction preview + Obsidian destination + apply/edit/reject), Escalation Queue (task/agent/reason/status table + copy-handoff/open-repo), Tool Safety (runtime guardrail rows + recent tool calls + emergency lock), Calendar candidates (approved filter + .ics export).

---

## 9. Empty / loading / error states
- **Loading:** boot orb splash during cold transpile; inline shimmer bars for classifying files; budget bar for research.
- **Empty:** `EmptyState` (icon tile + title + one line) — e.g. "Inbox clear", "No file selected".
- **Error / blocked:** red sphere state, red `denied` in tool log, runtime-unavailable degradation messaging.

---

## 10. Accessibility & readability
- Min UI text 11px (labels only); body 13–14px. High contrast: primary text ≥ `0.96` L on ≤ `0.21` L surfaces.
- Mono reserved for machine data so paths/counts are scannable.
- `:focus-visible` ring in `--live`. Keyboard: ⌘K palette, arrow/enter nav, Enter-to-send, Esc-to-close.
- `prefers-reduced-motion` collapses all animation. Status is never color-only — dots pair with text labels (READY/IDLE/etc.), badges carry words.

---

## 11. Tweakable parameters (in-design)
Accent hue (cyan/azure/indigo/teal) · base temperature (cool/neutral/warm) · density (compact/comfortable) · sphere style (orb/rings/minimal) · font pairing (grotesk/hanken/archivo). All map to root CSS vars at runtime.

---

## 12. File structure (prototype)
```
design_mockup/
  Brain UI.html      entry — fonts, theme, React/Babel, module load order
  theme.css          design tokens + primitives
  data.jsx           mock state (states, modes, system, nav, sample content)
  icons.jsx          stroke glyph set
  sphere.jsx         AgentSphere (state model + variants)
  components.jsx      shared components
  dashboard.jsx      Dashboard screen
  agent.jsx          Local Agent cockpit
  inbox.jsx          Raw Inbox
  stubs.jsx          semi-built + structured stub screens
  tweaks-panel.jsx   Tweaks shell
  app.jsx            shell: sidebar, top bar, palette, routing, tweak wiring
```

**Implementation mapping:** tokens → Tailwind theme extension + CSS vars; components → shadcn/ui primitives (Button, Badge, Dialog→palette, DropdownMenu→mode, Table, Tabs); sphere → standalone SVG/Canvas component bound to the agent-state store; agent state + mode → a single global store fed by `/api/agent/status`.
