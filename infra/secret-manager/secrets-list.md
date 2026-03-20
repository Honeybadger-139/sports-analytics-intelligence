# Secret Manager Inventory

Create these secrets in Google Secret Manager for production deployments.

| Secret ID | Value | Used by |
|-----------|-------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://...` | API, trainer, predictor, ingestion |
| `GEMINI_API_KEY` | `AIza...` | RAG, chatbot, embeddings |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` | Observability |
| `PREFECT_API_KEY` | `pnu_...` | Prefect worker / agent |
| `GRAFANA_ADMIN_PASSWORD` | generated secret | Grafana |
