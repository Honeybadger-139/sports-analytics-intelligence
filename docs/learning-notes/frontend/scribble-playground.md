# Scribble Playground — Learning Notes

> 📌 **Status**: Implemented on `scribble` branch, merged into `ui-redesign`.
> **Commit**: `c96fffd`
> **Linear**: SCR-146

---

## What Is Scribble?

A three-tab raw data playground embedded in `frontend-v2`. It lets analysts explore database tables and run custom SQL queries without leaving the dashboard.

```
Scribble
├── Explorer tab     ← Browse any raw table with filters and pagination
├── SQL Lab tab      ← Write and run SELECT queries with a monospace editor
└── Notebooks tab    ← Save, load, and delete named SQL queries (localStorage)
```

**Why "Scribble"?** It is intentionally informal — a scratchpad for data exploration, not a formal reporting tool. The name signals its purpose to users.

---

## Backend: Read-Only SQL API

### `POST /api/v1/scribble/query`

Security constraints enforced at the application layer:

| Constraint | Implementation |
|---|---|
| SELECT only (no DML/DDL) | Regex whitelist: `^SELECT\b` |
| No dangerous keywords | Blocklist: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `TRUNCATE`, `ALTER`, `CREATE`, `EXEC` |
| 500-row cap | `LIMIT 500` appended if not already present |
| 10-second timeout | `SET LOCAL statement_timeout = '10s'` |
| Read-only transaction | `SET TRANSACTION READ ONLY` wraps every query |

**Why application-layer security instead of PostgreSQL RLS?**

PostgreSQL Row-Level Security (RLS) would require:
- A separate read-only DB user (credential management overhead)
- Schema changes outside the current Docker Compose config
- Role setup that adds operational complexity

Application-layer validation achieves the same security contract (SELECT-only, row-capped) with zero infrastructure changes. Defense-in-depth would combine both — noted as future hardening.

**Interview framing**: "I applied the 80/20 security principle: application-layer validation covers all practical attack vectors with zero infra changes. Production hardening adds RLS as a second layer."

---

## Frontend Architecture: Component Decomposition

### 4 components + 1 reusable grid

```
Scribble.tsx (page)
├── TableBrowser.tsx    ← Explorer tab: table list sidebar + paginated rows
├── SqlLab.tsx          ← SQL Lab tab: editor + results
├── NotebooksPanel.tsx  ← Notebooks tab: saved query CRUD
└── DataTable.tsx       ← Reused by TableBrowser AND SqlLab for grid rendering
```

### Why extract `DataTable`?

`DataTable` renders any array of rows with:
- Client-side column filtering
- Sort by any column (asc/desc toggle)
- NULL cell display (`—`)
- Pagination controls

Without extracting it, the grid logic would be copy-pasted into both `TableBrowser` and `SqlLab`. The single component is the canonical grid — behaviour changes propagate everywhere automatically.

**Single Responsibility Principle applied**: `DataTable` renders data. It does not know where the data came from (REST API vs SQL query). `TableBrowser` and `SqlLab` own the fetching; `DataTable` owns the display.

---

## `useScribble.ts` Hook Collection

Four hooks, each responsible for one data concern:

| Hook | Purpose |
|---|---|
| `useTableList` | `GET /api/v1/raw/tables` — table names + row counts |
| `useTableRows` | `GET /api/v1/raw/{table}` — paginated rows for selected table |
| `useSqlQuery` | `POST /api/v1/scribble/query` — execute SQL, return columns + rows |
| `useNotebooks` | Read/write named queries to `localStorage` |

**API reuse principle (Explorer tab)**: The Explorer reuses the existing `/api/v1/raw/tables` and `/api/v1/raw/{table_name}` endpoints rather than creating new Scribble-specific routes. Those endpoints already enforce the `RAW_TABLES` whitelist and pagination. DRY at the API layer.

---

## localStorage Notebooks

### Why not PostgreSQL for notebooks?

Notebooks are personal, single-user session data at this stage:
- Zero backend changes needed
- Zero-latency read/write
- Data survives page refreshes
- No schema migration required

**Migration path**: When multi-user or team-shared notebooks are needed, migrate `useNotebooks` to `POST /api/v1/notebooks` — the hook interface stays identical, only the storage mechanism changes. The data model is already typed (`SavedNotebook`).

### Structure

```ts
interface SavedNotebook {
  id: string;         // uuid
  name: string;
  sql: string;
  savedAt: string;    // ISO timestamp
}
```

Stored in `localStorage` under key `sai_notebooks`. Serialised as JSON array.

---

## Cross-Tab Communication: CustomEvent Bus

### The problem

SQL Lab and Notebooks need to coordinate: clicking "Load" in Notebooks should populate the SQL editor in SQL Lab and switch to that tab.

**Options considered**:

| Option | Problem |
|---|---|
| Prop drilling from `Scribble.tsx` | Tight coupling — all tabs depend on parent state shape |
| Zustand / Context | Overkill for a single cross-tab signal |
| URL query params | Adds routing complexity, pollutes browser history |
| **CustomEvent** | Zero dependencies, keeps tabs self-contained |

### Implementation

```ts
// NotebooksPanel.tsx — dispatch when "Load" is clicked
window.dispatchEvent(new CustomEvent('scribble:load-sql', {
  detail: { sql: notebook.sql }
}));

// SqlLab.tsx — listen and populate editor
useEffect(() => {
  const handler = (e: CustomEvent) => {
    setSql(e.detail.sql);
    onTabChange('sql-lab');  // switch to SQL Lab tab
  };
  window.addEventListener('scribble:load-sql', handler as EventListener);
  return () => window.removeEventListener('scribble:load-sql', handler as EventListener);
}, []);
```

**Why CustomEvent is appropriate here**: Each tab component is independently renderable and testable. The event is a named, scoped message — structurally identical to how microservices communicate via message queues. The tradeoff is reduced traceability vs explicit state; mitigated by using a single well-named event (`scribble:load-sql`).

---

## SQL Lab Editor Features

- Monospace font (Fira Code from design system)
- Line numbers (rendered in a positioned `<pre>` overlay)
- `Cmd+Enter` / `Ctrl+Enter` shortcut to run query
- `Tab` key inserts 2 spaces (no focus trap)
- 4 example queries pre-loaded as collapsible chips
- Error display shows backend error message inline
- "Save" button opens a name prompt → stores to Notebooks

---

## Design Token: Emerald `#10B981`

Scribble shares `--accent-lab: #10B981` (emerald) with the Lab section. Both deal with raw data exploration — using the same accent colour signals their shared data-layer identity to users.

---

## Navbar Update

After Scribble was implemented:
- Removed the "Soon" badge from the Scribble nav item in `Navbar.tsx`
- Added `scribble` to the `liveIds` array in `Overview.tsx` so the directory card no longer shows a "Coming Soon" state

---

## Interview Angles

> "I applied the Single Responsibility Principle to the Scribble components. `DataTable` renders data; it doesn't know whether the data came from a REST API or a SQL query. This allowed me to reuse it in both the Explorer and SQL Lab without duplication."

> "I secured the SQL API at the application layer: regex whitelist for SELECT, blocklist for DML/DDL, read-only transaction wrapper, 500-row cap, and 10-second timeout. This is the 80/20 security solution — full coverage with zero infra changes."

> "I chose localStorage for notebooks because the use case is single-user session data. The data model is typed and the hook interface is stable — migrating to a Postgres backend later requires changing only the implementation inside `useNotebooks`, not any consumer."

> "The cross-tab CustomEvent is the lightest possible coupling mechanism. Each tab is independently testable; they coordinate via a named message, not shared state. Same pattern as microservice event buses at a micro scale."

## Interview Questions

1. Why did you choose application-layer SQL validation over PostgreSQL RLS?
2. How would you add a second layer of defense (RLS) without changing the frontend?
3. Why is `DataTable` a standalone component instead of being inlined?
4. What are the tradeoffs of using `localStorage` for notebook persistence?
5. When would you migrate notebooks from `localStorage` to a database?
6. Why use a CustomEvent for cross-tab communication instead of lifting state to the parent?
7. How would you extend Scribble to support multi-user shared notebooks?
