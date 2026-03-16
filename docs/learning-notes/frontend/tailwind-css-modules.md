# Learning Note: Tailwind v3 + CSS Modules in a Brownfield React App

**Module:** Frontend — CSS Architecture
**Date:** 2026-03-14
**Implemented in:** Wave 4 (SCR-299)

---

## What Is It?

**Tailwind CSS** is a utility-first CSS framework. Instead of writing named classes with custom styles, you compose utilities directly in JSX:
```tsx
// Traditional CSS approach
<div className="card">...</div>       // .card { background: #1a1a1a; padding: 16px; }

// Tailwind approach
<div className="bg-bg-panel p-4">...</div>  // no .css file needed
```

**CSS Modules** is a build-time feature (supported natively by Vite) that locally scopes CSS class names by transforming them into unique hashes:
```css
/* Button.module.css */
.btn { background: red; }
/* Compiled to: .btn_a3f9x2 { background: red; } */
```

```tsx
import styles from './Button.module.css'
<button className={styles.btn}>   // → class="btn_a3f9x2"
```

---

## Why Does It Matter?

### The Problem: Global CSS at Scale

Global CSS (one big `.css` file) has a fundamental flaw — **there's no isolation**. Any `.metric-card` rule you write applies to every element with that class everywhere in the app. This causes:

1. **Naming collisions** — Two components that both need a `.card` class silently override each other
2. **Ghost styles** — You delete a component but its CSS stays in the bundle (no dead-code elimination)
3. **Fear of refactoring** — "Is that class used somewhere else? I'm afraid to change it"
4. **Bundle bloat** — 88KB of CSS loaded on every page, even for styles used on only one route

Tailwind + CSS Modules solves all four.

---

## How Does It Work?

### Tailwind v3 Pipeline (PostCSS)

Vite feeds CSS through PostCSS plugins at build time:

```
Your CSS files
      ↓
PostCSS (postcss.config.js)
  → tailwindcss plugin: scans content files for class names → injects used utility CSS
  → autoprefixer plugin: adds -webkit- / -moz- vendor prefixes
      ↓
Final CSS bundle
```

**JIT (Just-In-Time) compilation** — Tailwind only includes CSS for classes you actually use. If you never write `bg-purple-700`, that rule is never in the bundle.

### CSS Modules (Vite native)

Vite automatically handles `.module.css` files — no plugin needed:

1. At build time, Vite transforms each class name in a `.module.css` file to a unique scoped identifier
2. The JS module import returns a mapping object: `{ 'metric-card': 'Overview_metric-card__a3f9x' }`
3. You reference it in JSX: `styles['metric-card']` → the scoped class name

### CSS Custom Properties as Design Tokens

Our design system uses CSS variables (`:root { --bg-base: #0d0d0e; }`). Tailwind's config bridges these:

```js
// tailwind.config.js
colors: {
  'bg-base': 'var(--bg-base)',   // → bg-bg-base utility
  accent: 'var(--accent)',        // → text-accent, border-accent utilities
}
```

**Why this is crucial:** CSS custom properties are evaluated at *runtime* by the browser. When the user switches to light mode (`body.theme-light`), the CSS vars change values, and every Tailwind utility that references them automatically reflects the new theme — zero JS needed.

---

## When to Use Each Approach?

| Situation | Best Tool | Reason |
|---|---|---|
| Simple layout utilities (flex, grid, padding, margin) | Tailwind utilities | No file needed; instant visual feedback |
| Component-specific styles with hover/focus states | CSS Modules | Scoping prevents collision; keeps component logic co-located |
| Pseudo-elements (`::before`, `::after`) | CSS Modules | Tailwind pseudo-element support is limited for complex shapes |
| `@keyframes` animations | CSS Modules | Animations need named keyframe blocks; easier in pure CSS |
| Styles shared across multiple pages (`.page-shell`) | Global CSS | CSS Modules scope would prevent reuse |
| Light/dark theme token overrides | CSS custom properties (`:root`) | Runtime evaluation required — can't replace with Tailwind config |

---

## The Brownfield Migration Pattern

A "brownfield" project is one that already has working code you don't want to break. Migrating a 2,000-line global CSS file all at once is high-risk. The **strangler fig pattern** is the solution:

```
Old System (global index.css)
    ↓ ← New System wraps around it incrementally
New System (CSS Modules per component)
```

**Phase 1:** Install Tailwind alongside existing CSS. Both coexist. No breakage.
**Phase 2:** Extract highest-traffic components first (Navbar, Overview, Chatbot).
**Phase 3:** (Future) Extract Arena, Lab, Scribble.
**Phase 4:** (Future) Delete global CSS rules that are now fully replaced.

At every phase, the app is deployable. You never have a "big bang" rewrite that breaks everything.

---

## Implementation Details in GameThread

### `preflight: false`

Tailwind's `preflight` is a CSS reset (based on normalize.css). We disable it because GameThread already has a hand-crafted reset in `index.css`. Two resets fighting each other would break typography and box-model assumptions.

```js
corePlugins: { preflight: false }
```

### Light-Theme Overrides in CSS Modules

CSS Modules are locally scoped — but `body.theme-light` is a global class. To target it from within a module:

```css
/* Chatbot.module.css */
:global(body.theme-light) .chat-bubble--user {
  background: rgba(146, 64, 14, 0.08);  /* amber-950/8% for light mode */
}
```

The `:global()` escape hatch tells CSS Modules: "don't scope this selector — match the global DOM."

### Multi-Class Pattern

When a component needs conditional or multiple module classes:
```tsx
className={[
  styles['metric-card-value'],
  m.mono ? styles.mono : '',
  m.valueClass ? styles[m.valueClass] : '',
].join(' ')}
```

Or with template literals for two classes:
```tsx
className={`${styles['chat-bubble']} ${styles['chat-bubble--ai']}`}
```

---

## Common Interview Questions

**Q: What's the difference between Tailwind and CSS Modules? Can you use both?**

*Junior answer:* Tailwind is utility classes, CSS Modules scope your CSS. Yes, you can use both.

*Senior answer:* They solve different problems. Tailwind eliminates the need for most hand-written CSS by giving you composable utilities — great for spacing, layout, and color. CSS Modules solve the scoping problem: they guarantee a component's class names can't collide with another component's, and they enable dead-code elimination at the component level. Using both is the industry-standard approach for large React apps — Tailwind for utilities, CSS Modules for component-specific styles that need pseudo-elements, animations, or complex selectors.

---

**Q: How does Tailwind work with a dark/light theme system based on CSS variables?**

*Junior answer:* You can use Tailwind's `dark:` variant.

*Senior answer:* Tailwind's `dark:` variant is great for simple two-mode themes, but it requires either a `prefers-color-scheme` media query or a `dark` class on `<html>`. If your design system already uses CSS custom properties with a class-toggle pattern (e.g., `body.theme-light`), the better approach is to bridge the CSS vars into Tailwind's config:

```js
colors: { 'bg-base': 'var(--bg-base)' }
```

Now `bg-bg-base` is a Tailwind utility that delegates color resolution to the runtime CSS variable. When `body.theme-light` flips the var's value, every Tailwind utility that references it automatically updates — zero JS, zero build step.

---

**Q: In a brownfield migration, how do you avoid a big-bang rewrite?**

*Junior answer:* Do it gradually.

*Senior answer:* Use the strangler fig pattern. Install the new system (Tailwind + CSS Modules) alongside the existing global CSS — both can coexist in the same Vite build. Then extract components by risk/traffic priority: start with the highest-traffic, lowest-interdependency components first. Each extraction is independently deployable. The codebase deliberately lives in a hybrid state during the migration — this is not technical debt, it's a controlled incremental rollout with a clear completion path. Never let "100% migration" block shipping.

---

**Q: What is JIT compilation in Tailwind v3?**

*Junior answer:* It generates CSS on demand.

*Senior answer:* JIT (Just-In-Time) compiler scans your content files at build time using static analysis — it looks for class name strings in HTML, JSX, and JS files. It only emits CSS rules for classes it finds. The result: the final CSS bundle only contains rules you actually use, regardless of how large Tailwind's full ruleset is. This means you can write `text-[#06C5F8]` (arbitrary values) and JIT will generate exactly that one rule — something the old Tailwind v2 with PurgeCSS couldn't do for dynamically composed class names.

---

## Gotchas and Production Concerns

1. **Dynamic class names don't work with Tailwind JIT.** If you compose a class name dynamically — `className={\`text-${color}\`}` — JIT can't detect it at build time and won't include the rule. Always use complete class names: `color === 'red' ? 'text-red-500' : 'text-green-500'`.

2. **CSS Modules bracket notation is required for kebab-case names.** `styles.metric-card` is invalid JS (minus sign). Use `styles['metric-card']` instead. Camelcase names (`styles.metricCard`) work with dot notation but only if the CSS file uses camelCase.

3. **`@keyframes` must be in the same module file as the class that uses them** — or in a global file. CSS Modules don't share keyframe names across files.

4. **Specificity battles with `!important`.** If your migrated module CSS has lower specificity than remaining global CSS, you'll get unexpected overrides. Check specificity when you notice a style not applying.

5. **Build time increases with large content scan.** If `content` in `tailwind.config.js` is too broad (e.g., `./src/**/*`), the JIT scanner parses every file. Keep it scoped to `{js,ts,jsx,tsx}`.

---

## Architecture Decision Summary

| Decision | Choice | Alternative | Reason |
|---|---|---|---|
| CSS framework | Tailwind v3 | styled-components, Sass modules | Zero runtime cost; JIT gives smallest bundle; CSS variable bridge enables runtime theming |
| Reset strategy | `preflight: false` | Enable preflight | GameThread already has its own reset — two resets conflict |
| Migration pace | Brownfield / strangler fig | Big-bang rewrite | High-risk rewrite avoided; each extraction is independently shippable |
| Design tokens | CSS custom properties (runtime) | Tailwind config values (build-time) | Runtime vars required for class-toggle theming without JS |
| Component scoping | CSS Modules | BEM, global named classes | Build-time scoping; Vite native; zero naming collisions |
