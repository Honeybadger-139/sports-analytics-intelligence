# UI Redesign — Learning Notes (`frontend`)

> 📌 **Status**: Active on `ui-redesign` branch. Not yet merged to `main`.
> **Commits**: `24312be` (scaffold) · `0e848c9` (logo redesign)
> **Linear**: SCR-143 · SCR-144

---

## Why React + Vite + TypeScript?

### The trigger
The vanilla `frontend/index.html` was approaching its scaling ceiling:
- The Chatbot requires an AbortController lifecycle, message history state, and streaming UI — painful in vanilla JS.
- The Scribble playground needs three coordinating tabs with shared state (SQL Lab ↔ Notebooks).
- Framer Motion mega-menus and animated route transitions cannot be replicated cleanly in plain JS.

### Vite (build tool / dev server)
- Sub-second Hot Module Replacement (HMR) — browser updates instantly on save.
- Native ESM during development, optimised Rollup bundle for production.
- Configured proxy: `/api/v1/*` → `http://localhost:8000` so the frontend never has CORS issues in dev.

### React 18 (UI framework)
- Component model: each section (`Chatbot`, `Scribble`, `Overview`) is self-contained.
- Custom hooks: `useApi`, `useChatbot`, `useScribble` isolate side effects and state from rendering.
- Framer Motion integration is React-native — `AnimatePresence` and `motion.div` handle mega-menu lifecycle.

### TypeScript
- Every API response is typed in `src/types.ts`.
- Compile-time checks prevent "passed number, expected string" bugs across 10+ backend endpoints.
- IDE autocompletion across components dramatically speeds up development.

---

## Project Structure

```
frontend/
├── index.html              ← Vite entry, loads Google Fonts
├── vite.config.ts          ← port 5174, /api proxy to :8000
├── src/
│   ├── main.tsx            ← React root render
│   ├── App.tsx             ← React Router routes
│   ├── types.ts            ← All API response types
│   ├── index.css           ← Global design system + component styles
│   ├── components/
│   │   ├── Navbar.tsx      ← Sticky navbar + Framer Motion mega-menu
│   │   ├── SportsMark.tsx  ← Animated SVG logo (symbol only)
│   │   └── Scribble/       ← DataTable, TableBrowser, SqlLab, NotebooksPanel
│   ├── hooks/
│   │   ├── useApi.ts       ← Generic polling fetch hook
│   │   ├── useChatbot.ts   ← Chat state + AbortController lifecycle
│   │   └── useScribble.ts  ← Table list, rows, SQL query, notebooks hooks
│   └── pages/
│       ├── Overview.tsx    ← Metric cards + navigation directory
│       ├── Pulse.tsx       ← Stub landing page
│       ├── Arena.tsx       ← Stub landing page
│       ├── Lab.tsx         ← Stub landing page
│       ├── Scribble.tsx    ← 3-tab data playground (live)
│       └── Chatbot.tsx     ← AI assistant full page (live)
```

---

## SportsMark SVG Logo

### Design principles
- Symbol only, no text — scales identically at 16px or 200px.
- 60×60 viewBox for crisp detail at all rendered sizes.
- Inspired by reference sports betting brand logo (clustered equipment).

### 6 sports equipment pieces

| Equipment | Color | Role in composition |
|---|---|---|
| Hockey stick + puck | Gold `#FFB300` | Background diagonal — largest element |
| Soccer ball | Blue-gray | Left, behind basketball |
| American football | Brown `#C47A2B` | Right, behind basketball, tilted |
| Baseball | Gray + red stitches | Top-right accent |
| Tennis ball | Cyan `#06C5F8` | Bottom-right accent |
| Basketball | Orange `#FF5C1A` | Centre foreground — hero / brand colour |

### 4 layered CSS animations

| Animation | Target | Duration | Effect |
|---|---|---|---|
| `spinRing` | Outer dashed circle | 22s | Clockwise rotation |
| `floatCluster` | Full equipment group | 3.5s | Gentle up/down float |
| `spinSeams` | Basketball seam lines | 11s | Seams rotate = ball appears to roll |
| `pulseGlow` | Outer orange glow ring | 2.8s | Fade in/out pulse |

### Key technique: CSS animations inside `<style>` in SVG
React SVG components can embed a `<style>` tag directly in the SVG for keyframe animations. This is cleaner than Framer Motion for continuous ambient animations and avoids re-renders.

---

## Navbar Architecture

### Layout zones

```
[SportsMark]  |  [Pulse · Arena · Lab · Scribble · Chatbot]  |  [Status pill · Theme toggle]
   left               center (flex: 1, justify-content: center)         right
```

### Mega-menu flyout (Framer Motion)

```tsx
// Simplified pattern
const [open, setOpen] = useState<string | null>(null);

<AnimatePresence>
  {open === item.id && (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.18 }}
    >
      {/* sub-item grid */}
    </motion.div>
  )}
</AnimatePresence>
```

- Opens on hover (`onMouseEnter`) or click (mobile fallback).
- Click-outside detection via `useEffect` + `mousedown` listener on `document`.
- Each nav item has a per-section accent colour dot: orange, cyan, emerald, amber.

### System status pill
Polls `GET /api/v1/system/status` every 30s. Maps response to one of four states:

| Status | Color | Condition |
|---|---|---|
| Healthy | Green | DB connected, pipeline recent |
| Degraded | Yellow | Pipeline stale or partial failures |
| Error | Red | DB unreachable or API error |
| Connecting | Gray | Initial load |

---

## Overview Page

### Zone 1 — Live Metric Cards
8 cards polled from the backend every 30s via `useApi`:

| Card | Source endpoint |
|---|---|
| Database | `/api/v1/system/status` |
| Pipeline | `/api/v1/system/status` |
| Matches | `/api/v1/matches` |
| Features | `/api/v1/system/status` |
| Players | `/api/v1/system/status` |
| Bankroll | `/api/v1/bets/summary` |
| ROI | `/api/v1/bets/summary` |
| Open Bets | `/api/v1/bets/summary` |

### Zone 2 — Navigation Directory
One card per section. Each card shows:
- Section name + accent colour + icon
- One-line description of what it does
- Bulleted list of sub-items
- "Explore →" link (React Router `<Link>`)

Acts as both an onboarding page for new users and a quick-access directory for power users.

---

## Design System (`index.css`)

### CSS custom properties (design tokens)

```css
:root {
  --bg-primary:   #05090F;   /* near-black base */
  --bg-surface:   #0D1520;   /* card/panel surface */
  --bg-elevated:  #162030;   /* elevated elements */
  --text-primary: #F0F4FF;
  --text-muted:   #6B7A99;

  /* Per-section accents */
  --accent-pulse:   #FF5C1A;  /* orange */
  --accent-arena:   #06C5F8;  /* cyan */
  --accent-lab:     #10B981;  /* emerald */
  --accent-scribble:#10B981;  /* emerald (shared with Lab) */
  --accent-chat:    #F59E0B;  /* amber */

  /* Semantic */
  --success: #22C55E;
  --warning: #F59E0B;
  --error:   #EF4444;
}
```

### Fonts
- **Bebas Neue** — condensed display, section headers
- **Syne** — clean UI body text
- **Fira Code** — monospace for data values, SQL editor

### Light theme
`body.theme-light` overrides key tokens — backgrounds invert to near-white, text darkens. Accent colours remain the same. Preference persisted in `localStorage` as `sai_theme`.

---

## `useApi` Hook Pattern

```ts
function useApi<T>(url: string, intervalMs = 30000): { data: T | null; loading: boolean; error: string | null }
```

- Initial fetch on mount.
- Polling interval via `setInterval`.
- Cleanup on unmount (no memory leaks).
- Returns `{ data, loading, error }` — components destructure what they need.

---

## Branch Strategy (Staging → Production Pattern)

```
main (production)
  └── ui-redesign (staging)
        ├── chatbot   ← merged: chatbot UI + backend
        └── scribble  ← merged: data playground
```

**Development**: `frontend/` on port 5174, `frontend/` served by FastAPI on 8000. Two UIs coexist.

**Promotion flow** (when UI is approved):
1. Delete `frontend/` from `ui-redesign` branch.
2. Rename `frontend/` → `frontend/`.
3. Merge `ui-redesign` → `main`.

Git sees it as the contents of `frontend/` changing — same as any other file replacement. Identical to a staging → production deploy.

---

## Interview Angles

> "I scaffolded the React frontend in a parallel branch using the strangler fig pattern — production continued running while the new UI matured in isolation."

> "Vite's dev proxy forwards `/api/v1/*` to the FastAPI backend, so the frontend never hits CORS issues in development. The same config works in production with a reverse proxy."

> "The SportsMark logo is an SVG with embedded CSS keyframes — four animations layered on different elements. No JavaScript, no re-renders, zero runtime cost."

> "The Framer Motion mega-menu uses `AnimatePresence` for mount/unmount animations. Without it, the exit animation would never run because React removes the DOM element before CSS can play it."

## Interview Questions

1. Why use Vite instead of Create React App or Next.js?
2. How does the dev proxy in `vite.config.ts` prevent CORS issues?
3. What is `AnimatePresence` and why is it needed for exit animations?
4. How does the `useApi` polling hook prevent memory leaks on unmount?
5. Why embed CSS keyframes inside the SVG `<style>` tag instead of using Framer Motion?
6. How would you promote `frontend` to production without a deployment downtime window?
