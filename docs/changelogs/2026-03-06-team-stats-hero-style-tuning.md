# 2026-03-06 - Team Stats hero style tuning (logo + naming emphasis)

## Type
UI enhancement (frontend visual tuning)

## Goal
Match the requested presentation style for Team Stats detail view: larger team logo and stronger team-name emphasis in the header area.

## What changed
- Updated `frontend/src/components/Arena/TeamStatsView.tsx` team header:
  - Replaced compact header row with a hero-style card layout.
  - Increased logo size in header to `84`.
  - Increased team name typography (`var(--font-display)`, larger size).
  - Added compact identity chips (`USA`, abbreviation, season scope).
  - Preserved `Create Dashboard` action in the hero block.

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-195`
