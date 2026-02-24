import logging
from src.data.ingestion import get_engine, ingest_player_game_logs
logging.basicConfig(level=logging.INFO)
engine = get_engine()
dash = ingest_player_game_logs(engine, "2025-26")
