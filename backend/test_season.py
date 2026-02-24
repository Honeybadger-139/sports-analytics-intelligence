import logging
from src.data.ingestion import get_engine, ingest_player_season_stats
logging.basicConfig(level=logging.INFO)
engine = get_engine()
dash = ingest_player_season_stats(engine, "2025-26")
