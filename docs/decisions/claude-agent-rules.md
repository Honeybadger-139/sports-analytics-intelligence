# Claude Agent Rules
> Persistent backup of all rules stored in Claude's memory system.  
> Save this file at `docs/decisions/claude-agent-rules.md` in every project.  
> If Claude memory is ever reset, re-feed this file at the start of a session.

---

## 1. Teaching Rules
*Applies to: all projects and learning sessions*

- **Before any code**, explain WHAT we're building and WHY in plain language
- Use analogies and real-world examples
- Teach at **Senior Manager / Architect level** — focus on WHY and WHEN, not just HOW
- Always **compare approaches**: "We could use A, B, or C. Here's why B fits our case..."
- Cover scalability, production concerns, and real-world gotchas
- **Quiz** after each phase with potential interview questions
- Highlight the difference between a **junior answer** and a **senior answer**
- Point out **"awe moment" insights** — things that make interviewers lean forward

---

## 2. Documentation Rules
*Applies to: all projects*

### Decision Log
- Update `docs/decisions/decision-log.md` for **every architectural or technical decision**
- Format:
  ```
  Decision → Alternatives Considered → Why This Choice → Trade-off → Interview Angle
  ```

### Learning Notes
- After each module, create/update a note in `docs/learning-notes/`
- Each note must cover:
  - What is it?
  - Why does it matter?
  - How does it work? (intuition, not just math)
  - When to use vs alternatives?
  - Common interview questions
  - Senior Manager / Architect perspective

### File Structure
| Content | Location |
|---|---|
| Architecture designs | `docs/architecture/` |
| Decisions & decision log | `docs/decisions/` |
| Learning notes | `docs/learning-notes/` |
| Diagrams & images | `docs/images/` |
| These agent rules | `docs/decisions/claude-agent-rules.md` |

> ⚠️ **NEVER store important knowledge only in conversation memory — always persist to files.**

---

## 3. Session Start Rules
*Applies to: every project session*

1. Read `docs/decisions/decision-log.md` first to restore context
2. Read relevant learning notes for the current module
3. Work in **phases** — don't jump ahead
4. After each phase: summarize learnings + quiz on interview questions
5. Current project: **Sports Analytics Intelligence Platform** (Linear team: Personal)

### Tone
- Be direct and honest — correct mistakes without sugarcoating
- No fluff or motivation speeches — real knowledge only
- Use **"What would you do if..."** scenarios to build interview readiness

---

## 4. Linear Agent Rules
*Applies to: all code changes and project sessions*

### Rule 1 — User-Requested Change: Issue BEFORE File Edits
If the user requests any code change:
1. Call `create_issue` in Linear **BEFORE** editing any files
2. Use the task description as the ticket title
3. Post the issue ID (e.g. `SAIP-123`) in chat to confirm sync
4. Only then proceed with file edits

### Rule 2 — Agent-Initiated Fix: Fix FIRST, Then Issue
If Claude proactively fixes a bug or improvement:
1. Apply the fix first
2. Immediately create an issue titled `"Fixed: [Description]"`
3. Post the issue ID in chat

### Rule 3 — Deferred / "Later": Create Issue + Abort Edits
If the user says "later", "defer", or "do this later":
1. Call `create_issue` immediately
2. **ABORT all file edits** — no write/edit tools until ticket is referenced
3. Resume only when the user explicitly references that ticket ID

### Rule 4 — Operational Silence (No Tickets For)
Do NOT create Linear issues for:
- `npm start` / `npm install`
- `docker-compose up`
- Kill port commands
- `git push` / `git commit`
- Environment variable setup

These are ephemeral tasks — no ticket needed.

### Rule 5 — Sync Confirmation
After every ticket creation, post the Linear issue ID in chat.  
**No ID posted = sync not confirmed = rule violated.**

---

## How to Restore These Rules After a Memory Reset

If Claude's memory is ever cleared, paste the following at the start of a session:

```
Please read docs/decisions/claude-agent-rules.md and treat all rules in it 
as your active operating instructions for this project session.
```

---

*Last updated: March 2026*
