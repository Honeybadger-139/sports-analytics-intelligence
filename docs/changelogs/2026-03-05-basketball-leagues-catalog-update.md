# 2026-03-05 - Basketball leagues catalog update (WNBA, NBL, MPBL)

## Type
Implementation (frontend config update)

## Change summary
Updated basketball league options in the global sport selector.

Added/confirmed basketball leagues:
- NBA
- WNBA
- NBL (Australia)
- MPBL (Philippines)
- G League (existing)

## Behavior
- Live data support remains unchanged:
  - Only `Basketball + NBA` is live.
  - All other leagues continue to show `Coming Soon` hold state.
- Coming Soon screen now explicitly surfaces basketball roadmap leagues when a non-NBA basketball league is selected.

## Files
- `frontend/src/config/sports.ts`
- `frontend/src/components/ComingSoonHold.tsx`

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-186`
