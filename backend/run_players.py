import sys
sys.path.insert(0, 'backend/src')
from data.ingestion import ingest_players, get_engine
import pandas as pd

engine = get_engine()
print("Running ingest_players standalone...")
ingest_players(engine, season="2024-25")
