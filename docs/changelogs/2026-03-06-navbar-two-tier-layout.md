# 2026-03-06 - Navbar two-tier layout (primary routes + context row)

## Type
UI enhancement (frontend navigation usability)

## Goal
Keep primary modules (including Pulse and Chatbot) consistently visible by separating module navigation from sport/league/season controls.

## What changed
- Updated `frontend/src/components/Navbar.tsx`:
  - Introduced two-tier shell:
    - `navbar-main`: logo + primary module navigation + system/theme controls
    - `navbar-context-row`: sport/league/season controls + support status
- Updated `frontend/src/index.css`:
  - Added navbar shell + row height tokens
  - Switched overall navbar height token to combined two-row height
  - Added context-row alignment/overflow behavior for responsive widths
  - Preserved mega-menu offset against total navbar height

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-197`
