# Navbar Status Proxy Hotfix

Date: 2026-03-04 (Asia/Kolkata)  
Scope: Fix false `ERROR` status pill in frontend navbar.

## Problem

- Navbar status showed `ERROR` even when backend service was healthy.

## Root Cause

- Frontend Vite proxy pointed to `http://localhost:8000`.
- Active backend was running on `http://localhost:8001`.
- Status request (`/api/v1/system/status`) failed through the frontend proxy.

## Fix

1. Updated proxy target in:
   - `frontend/vite.config.ts`
2. Changed:
   - from `http://localhost:8000`
   - to `http://localhost:8001`

## Verification

1. Started frontend dev server.
2. Verified proxied health endpoint:
   - `GET http://127.0.0.1:5175/api/v1/system/status`
   - Result: `200`
3. Opened frontend:
   - `http://127.0.0.1:5175/`

## Linear Tracking

- Implemented and logged under `SCR-180`.
