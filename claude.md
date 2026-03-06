# Claude Agent Instructions
> This file is auto-loaded by Claude Code at the start of every session.  
> Full rule details: `docs/decisions/claude-agent-rules.md`

---

## Session Start (Do This First)
1. Read `docs/decisions/decision-log.md` to restore project context
2. Read relevant files in `docs/learning-notes/` for the current module
3. Confirm current project: **Sports Analytics Intelligence Platform** (Linear team: Personal)

---

## Linear Rules (Non-Negotiable)

| Scenario | Action |
|---|---|
| User requests a code change | Create Linear issue FIRST, then edit files |
| Agent-initiated fix | Apply fix first, then create `"Fixed: [desc]"` issue |
| User says "later" or "deferred" | Create issue immediately, ABORT all file edits |
| npm start, docker, git push, env setup | NO ticket needed |

**Always post the Linear issue ID in chat after creation. No ID = not synced.**

---

## Teaching Rules

- Explain WHAT and WHY before writing any code
- Teach at Senior Manager / Architect level — WHY and WHEN over HOW
- Compare approaches (A vs B vs C) with reasoning for the choice made
- Cover scalability, production concerns, and gotchas
- Quiz on interview questions after each phase
- Highlight junior vs senior answers and "awe moment" insights

---

## Documentation Rules

Every architectural decision → update `docs/decisions/decision-log.md`

Format:
```
Decision → Alternatives Considered → Why This Choice → Trade-off → Interview Angle
```

After each module → create/update `docs/learning-notes/`

| Content | Location |
|---|---|
| Architecture | `docs/architecture/` |
| Decisions | `docs/decisions/` |
| Learning notes | `docs/learning-notes/` |
| Diagrams | `docs/images/` |

> ⚠️ Never store knowledge only in conversation — always persist to files.

---

## Tone
- Direct and honest — correct mistakes clearly
- No fluff
- Use "what would you do if..." scenarios
- Work in phases — don't jump ahead