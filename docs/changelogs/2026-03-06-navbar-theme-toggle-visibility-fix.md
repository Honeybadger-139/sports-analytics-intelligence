# 2026-03-06 - Navbar theme toggle visibility fix

## Type
Bug fix (frontend navbar layout)

## Problem
Theme toggle control existed in navbar logic but could be pushed out of view when navbar content overflowed, making it appear removed.

## Root cause
- Center nav section was allowed to consume layout width without constrained overflow behavior.
- Right control group (context/status/theme) could be displaced in tighter widths.

## What changed
- Updated `frontend/src/index.css` navbar layout behavior:
  - `navbar-nav`: constrained with `min-width: 0` and horizontal overflow scrolling (hidden scrollbar).
  - `navbar-right`: protected with margin/z-index and fixed shrink behavior.
  - `theme-btn`: explicit `flex-shrink: 0` and pointer cursor.
  - Responsive hardening (`<=960px`):
    - hide `status-pill`
    - tighten right-group spacing
    - slightly reduce theme button size

## Validation
- `cd frontend && npm run build` ✅

## Linear
- Issue: `SCR-196`
