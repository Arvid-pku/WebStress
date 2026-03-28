# Demo Site Layout Redesign

**Date:** 2026-03-28
**Scope:** Environment page, Trajectory page, Nav, global design language

## Overview

Redesign the demo site's Environment and Trajectory pages for full-width environment rendering, multi-environment support, and a softer modern design language. The current design uses narrow centered containers and a harsh monospace/uppercase aesthetic. The new design prioritizes immersive environment interaction with polished, rounded UI chrome.

## Design Language Changes

### From → To

| Element | Current | New |
|---------|---------|-----|
| Border radius | 4px | 10–14px (pills, cards, inputs, buttons) |
| Labels | Monospace, uppercase, letter-spacing 2-3px | Sans-serif (DM Sans), sentence case, font-weight 500 |
| Nav | Plain text links, `max-w-[1200px]` | Full-width, pill-shaped tab group with rounded bg |
| Metadata | Raw monospace text | Soft rounded pills with surface background |
| Monospace usage | Labels, metadata, headings | Code only (action JSON, scores, step numbers) |
| Email rows | `border-bottom` dividers | Rounded hover states, no dividers |
| Typography hierarchy | Letter-spacing tricks | Weight 500–600 for hierarchy |

### Design Tokens (unchanged)

Keep the existing oklch color palette and CSS custom properties (`--bg`, `--surface`, `--border`, `--text-primary`, `--text-secondary`, `--text-tertiary`, `--accent`, `--green`, `--red`). Light/dark theme support unchanged.

## Nav Redesign

**File:** `src/components/ui/Nav.tsx`

- Remove `max-w-[1200px] mx-auto` constraint — go full-width with `px-6`
- Replace plain text links with a pill-shaped tab group:
  - Container: `bg-[var(--surface)]` with `rounded-xl` and `p-1`
  - Active tab: `bg-[var(--bg)]` with `rounded-[10px]`, `font-weight-500`
  - Inactive tab: transparent, `text-secondary`
- External links (Paper, GitHub) stay as plain text on the right
- Theme toggle stays

## Environment Page Redesign

**File:** `src/app/environment/page.tsx`

### Current
- Narrow `max-w-[1200px]` container with hero header
- Gmail-only, task selector + instruction stacked above embed
- Gmail gets `calc(100vh - 120px)` height

### New: Multi-Environment Explorer

**Priority order:** env selection → full free interaction → task selection

**Layout (top to bottom, all full-width):**

1. **Environment selector strip** — horizontal bar with `bg-[var(--surface)]`, `border-bottom`
   - Pill-shaped env cards with `rounded-xl`
   - Available envs: green dot + full opacity
   - Unavailable envs: grey dot + `opacity-0.35` + `cursor-not-allowed`
   - 5 environments: Gmail (available), Robinhood, Project Manager, Social Media, Amazon (all coming soon)
   - Right side: task dropdown with "Free exploration (no task)" as default option

2. **Instruction bar** (conditional) — shown only when a task is selected (not "Free exploration")
   - Single-line: label "Instruction" + text + metadata badges (difficulty, steps) as rounded pills
   - `border-bottom` separator

3. **Environment embed** — fills all remaining viewport height
   - No wrapping border or rounded container — the environment IS the page
   - `flex: 1` in a full-height flex column

**Behavior:**
- "Free exploration" loads the environment with default seed state, no instruction shown
- Selecting a task loads the task fixture and shows the instruction bar
- Switching environments swaps the embed (only Gmail functional for now; others show a placeholder)

### Data Source

Pull environment list from the existing manifest (`build_manifest()` output). Each env has `env_id`, `title`, `available`. Tasks come from the existing `loadTaskManifest()` filtered by selected env.

## Trajectory Page Redesign

**File:** `src/app/results/[taskId]/TrajectoryPage.tsx`

### Current
- Full-width with fixed `grid-cols-[1fr_400px]` split
- Gmail left, trajectory/criteria panel right (always visible)

### New: Collapsible Slide-Over Sidebar

**Layout:**

1. **Top bar** (compact, full-width) — same content as current but with rounded badge styling:
   - Left: `← Results` link, task title, difficulty badge, score bar + pass/fail pill
   - Right: model name, step count, elapsed time
   - "Show task" button for instruction (toggleable, same as current)

2. **Main area** — Gmail fills full width, sidebar overlays from right

3. **Sidebar (open state, ~320px):**
   - Overlays Gmail (does not push/resize it)
   - `border-left` + `box-shadow` for depth
   - Tab bar: Trajectory / Criteria (same functionality as current)
   - Trajectory tab: vertical timeline with step numbers, action descriptions, thought previews
   - Active step: accent border-left, highlighted background
   - Criteria tab: same pass/fail list with penalty badges and related-step buttons
   - Bottom: "collapse" toggle

4. **Sidebar (collapsed state, 36px):**
   - Thin vertical strip with `border-left`
   - Vertical text label "Trajectory" (writing-mode: vertical-rl)
   - Toggle button to expand
   - Step counter moves to top bar (`step 2/12`)

5. **Target indicator bar** — stays below top bar, above Gmail. Shows current target element + action JSON.

**Animation:** CSS transition on sidebar width, ~200ms ease-out.

**Default state:** Sidebar open on page load.

## Results List Page

**File:** `src/app/results/page.tsx`

Minimal changes — apply the new design language only:
- Rounded corners on table rows (hover states)
- Sans-serif labels instead of monospace uppercase
- Metadata badges as rounded pills
- Keep the current `max-w-[720px]` centered layout (it's a data table, not an environment)

## Files to Modify

| File | Change |
|------|--------|
| `src/components/ui/Nav.tsx` | Full-width, pill tab group |
| `src/app/environment/page.tsx` | Multi-env explorer with full-bleed interaction |
| `src/app/results/[taskId]/TrajectoryPage.tsx` | Collapsible sidebar overlay |
| `src/app/results/page.tsx` | Design language updates (rounded, sans-serif) |
| `src/app/page.tsx` | Design language updates on landing page |
| `src/app/globals.css` | No structural changes needed |

## Out of Scope

- Building actual Robinhood/PM/Social/Amazon environments (just show coming-soon placeholders)
- Changing the Gmail environment's internal styling (`gmail.css`)
- Modifying the shared component library (`@webagentbench/shared`)
- Changing data fetching, fixtures, or backend
