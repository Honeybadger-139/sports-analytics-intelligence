# Wave 4 — Tailwind v3 + CSS Modules Migration

**Date:** 2026-03-14
**Linear:** SCR-299 (Wave 4)
**Status:** In Review

---

## Summary

Migrated the GameThread frontend from a monolithic 88KB `index.css` file to a hybrid architecture: Tailwind v3 PostCSS pipeline for utility-class authoring, paired with component-local CSS Modules for high-traffic components (Navbar, Overview, Chatbot). Total CSS footprint reduced from 88KB → 76KB with zero visual regressions.

---

## Problem Statement

`frontend/src/index.css` had grown to 2,004 lines (88KB) with no scoping — every rule was global. This caused:
- High collision risk: a `.metric-card` rule could accidentally affect any element with that class anywhere in the app
- Poor IDE discoverability: developers had to grep the monolith to understand what CSS applied to a component
- Bundle bloat: all CSS was loaded on every page even for styles that were only used on one route

---

## Approach: Brownfield Strangler Fig

Rather than rewriting all CSS at once (high-risk), we used the **strangler fig pattern**:
1. Install Tailwind v3 alongside the existing CSS — both coexist
2. Extract the 3 highest-traffic components first: Navbar, Overview, Chatbot
3. Leave Scribble/Lab/Arena CSS global — those have too many sub-components to migrate safely in one pass

This means the codebase is in a deliberate transitional state where some components use CSS Modules and some use global classes. Future waves will extract the remaining components.

---

## Changes

### Infrastructure

| File | Change Type | Purpose |
|---|---|---|
| `frontend/package.json` | Modified | Added `tailwindcss@^3.4.17`, `autoprefixer@^10.4.21`, `postcss@^8.5.3` |
| `frontend/tailwind.config.js` | New | Full CSS variable bridge — maps all design tokens to Tailwind utilities |
| `frontend/postcss.config.js` | New | PostCSS pipeline: `tailwindcss` → `autoprefixer` |
| `frontend/src/index.css` | Modified | Added `@tailwind base/components/utilities`; removed extracted CSS blocks |

### Key tailwind.config.js decisions

```js
// preflight: false — prevents Tailwind's CSS reset from conflicting with our global resets
corePlugins: { preflight: false }

// CSS variable bridge — Tailwind tokens reference CSS vars, so light/dark theming works automatically
colors: { 'bg-base': 'var(--bg-base)', accent: 'var(--accent)', ... }
```

### Component Extractions

**Navbar** — `src/components/Navbar.module.css` (180 lines)
- `.navbar-shell`, `.navbar`, `.navbar-main`, `.navbar-context-row`
- `.nav-item` with `.active` and `.open` sub-states
- `.mega-menu-overlay`, `.mega-menu-inner`, `.mega-menu-grid`, `.mega-sub-item`
- Light theme overrides via `:global(body.theme-light) .class`

**Overview** — `src/pages/Overview.module.css` (190 lines)
- `.overview-hero`, `.overview-title`, `.overview-subtitle`, `.overview-eyebrow`
- `.metrics-grid`, `.metric-card` (with `::before` accent stripe pseudo-element)
- `.dir-card` (with `::after` glow circle pseudo-element), `.dir-subitems`, `.dir-subitem`
- Status classes: `.status-healthy`, `.status-error`, `.status-degraded`

**Chatbot** — `src/components/Chatbot/Chatbot.module.css` (240 lines)
- `.chatbot-panel`, `.chatbot-sidebar`, `.chatbot-main`
- `.chat-bubble--ai/.chat-bubble--user/.chat-bubble--error`
- `.typing-dot` with `@keyframes typing-bounce`
- `.chatbot-sidebar-dot` with `@keyframes pulse-dot`

### Component Files Modified

| File | Change |
|---|---|
| `src/components/Navbar.tsx` | `import styles from './Navbar.module.css'`; all global class refs → `styles['class-name']` |
| `src/components/Chatbot/ChatbotPanel.tsx` | Same pattern |
| `src/components/Chatbot/ChatMessage.tsx` | Same pattern |
| `src/pages/Overview.tsx` | Same pattern |

**Multi-class pattern used throughout:**
```tsx
className={[styles['nav-item'], isActive ? styles.active : ''].join(' ')}
```

---

## Build Results

```
npm run build → ✅ 537 modules transformed
CSS: 88KB → 76KB (14% reduction)
JS: no change
```

Pre-existing lint warnings (15 `setState-in-effect` in Arena/Lab components) and 1 npm vulnerability were not introduced by this wave and remain unchanged.

---

## What Was NOT Migrated (Intentional)

| Component | Reason |
|---|---|
| Arena (predictions, SHAP, team stats) | Too many sub-components; requires dedicated wave |
| Lab (data quality, pipeline inspector) | Same |
| Scribble (SQL playground) | Same |
| Global `.status-pill` | Used across multiple pages — stays global by design |
| Global `.page-shell/.page-content` | Layout primitives — shared by all pages |

---

## Interview Angle

> "How do you migrate a legacy global CSS codebase to a modern architecture without breaking production?"

**Senior answer:** Use the strangler fig pattern — install the new system alongside the old one, extract components incrementally by traffic/risk priority, and maintain a deliberate transitional state. The key is: never let "perfect migration" block shipping. Extract the 3 most-used components first, validate, then continue. The brownfield hybrid (Tailwind + CSS Modules + remaining global CSS) is not technical debt — it's a controlled migration in progress with a clear completion path.
