# UI redesign foundation

Phase 1 lives on `feat/ui-revamp`. Continue later UI phases on this branch. The frontend remains React, Vite, Lucide, and CSS; the backend and API contracts were not changed.

## Where to work

- `src/styles/tokens.css`: shared dark palette, semantic colors, spacing, shape, elevation, and motion.
- `src/styles.css`: shared controls, panels, typography, statuses, and existing screen styles.
- `src/ui/primitives.tsx`: common panel, heading, loading, empty, error, fatal, and toast treatments.
- `src/shell/AppShell.tsx` and `src/shell/shell.css`: role-scoped navigation, sidebar, top bar, responsive frame, and skip link.
- `src/brand/BootSplash.tsx`: first-session-only, skippable, time-bounded brand cue.

Keep navigation labels and role configuration in `AppShell.tsx`. Keep case queries and role-switch cache reset in `App.tsx`. Future screen redesigns should consume tokens and primitives without moving calculations or authorization into the UI.

## Phase 1 boundaries

Portfolio, officer dossier, Company 360, and the network view retain their existing information architecture. Status color is semantic: amber for attention, green for accepted or resolved, red for errors, and cyan for interaction. A service mode such as `LIVE` is neutral.

The boot cue is configured for 1,000 ms on the first ordinary session load, with its fade in the final 180 ms. Reduced-motion users bypass the overlay. The application and network continue loading behind the cue.

## Validation

Run `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`, `npm --prefix frontend test -- --reporter=dot`, and `npm --prefix frontend run build`. Run `npm --prefix frontend run test:e2e` against the repository's isolated synthetic backend setup described in `.github/workflows/frontend.yml`. Check 320, 390, 768, 1440×900, and 1920×1080 layouts before changing the shell.
