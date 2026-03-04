# Dark Date Picker Icon Hotfix

Date: 2026-03-04 (Asia/Kolkata)  
Scope: Restore visible date-picker icon in dark mode.

## Problem

- Date fields were clickable (native picker tooltip appeared), but icon contrast in dark mode was too low.

## Fix

Updated:
- `frontend/src/index.css`

Changes:
1. Added explicit custom calendar icon as a background image for `input[type='date']` in dark mode.
2. Added matching light-mode calendar icon background.
3. Kept native picker interaction by leaving `::-webkit-calendar-picker-indicator` interactive with near-transparent opacity.
4. Preserved date text visibility and right-side spacing.

## Follow-up Correction (Same Day)

Issue observed after first patch:
- Some date inputs still had no visible icon because component-level inline `background` styles overrode CSS `background-image`.

Final approach:
1. Removed dependency on custom background-image icon.
2. Used native `::-webkit-calendar-picker-indicator` as the visible icon.
3. Set `opacity: 1` and explicit dark/light filter values for contrast.

## Validation

1. `cd frontend && npm run build`  
   Result: success (`tsc -b` + `vite build`)
2. Opened:
   - `http://127.0.0.1:5173/pulse/previews`

## Linear Tracking

- Implemented under `SCR-181`.
