# Frontend — Learning Notes

> 📌 **Status**: Implemented — System Health Dashboard with real-time pipeline monitoring.

## What Is the Frontend?

The Frontend is a premium HTML/CSS/JS dashboard that visualizes system health, pipeline audit trails, and data freshness. It communicates with the API Layer via `fetch()` calls.

## Current Implementation

### System Health Dashboard (`frontend/index.html`)
- **5 KPI Cards**: Database status, pipeline health, match count, feature count, active players
- **Audit History Table**: Paginated view of every pipeline run with timestamps, record counts, and errors
- **Auto-Refresh**: Polls `/api/v1/system/status` every 30 seconds
- **Animated Counters**: Smooth count-up animations on value changes

### Design Decisions
- **Dark Mode First**: Professional dark theme with glassmorphism card effects
- **No Framework**: Vanilla CSS + JS for zero build dependencies — static files served by FastAPI
- **Responsive**: Breakpoints for desktop (5 columns), tablet (2 columns), and mobile (1 column)

## Interview Angle

> "I built the frontend as a static HTML+CSS+JS dashboard served directly by FastAPI's StaticFiles mount. This eliminates the need for a separate build pipeline while still providing a premium visual experience. The glassmorphism design language uses CSS `backdrop-filter` for depth without JavaScript overhead."

## Future Topics (Phase 4)
- Match prediction cards with SHAP waterfall charts
- Bankroll tracking and performance analytics
- Chart libraries for time-series visualization
