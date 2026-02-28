import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# 🌍 PROJECT CONFIGURATION
# ==========================================

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://analyst:analytics2026@localhost:5432/sports_analytics",
)

# API Settings
# We use a 2s delay because NBA.com is very sensitive to scraping.
# If we fire requests too fast, we'll get blocked (429 Too Many Requests).
REQUEST_DELAY = 2.0  
MAX_RETRIES = 3      
BASE_BACKOFF = 10    

# Ingestion Settings
# Change this to pull different seasons (e.g., "2023-24")
CURRENT_SEASON = "2025-26"

# Directory Paths
import pathlib
_BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = _BACKEND_ROOT / "logs"
MODEL_DIR = _BACKEND_ROOT / "models"
DATA_DIR = _BACKEND_ROOT / "data"

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# Intelligence (Phase 4)
INTELLIGENCE_ENABLED = _env_bool("INTELLIGENCE_ENABLED", True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
RAG_MAX_AGE_HOURS = int(os.getenv("RAG_MAX_AGE_HOURS", "120"))
RAG_COLLECTION = os.getenv("RAG_COLLECTION", "nba_context_v1")
RAG_SUMMARY_MODEL = os.getenv("RAG_SUMMARY_MODEL", "gemini-2.0-flash")
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "models/embedding-001")
RAG_REQUEST_TIMEOUT_SECONDS = int(os.getenv("RAG_REQUEST_TIMEOUT_SECONDS", "8"))
RAG_CHROMA_DIR = pathlib.Path(os.getenv("RAG_CHROMA_DIR", str(DATA_DIR / "chroma")))
RAG_CHROMA_DIR.mkdir(parents=True, exist_ok=True)

INTELLIGENCE_SOURCES = _env_csv(
    "INTELLIGENCE_SOURCES",
    [
        "https://www.espn.com/espn/rss/nba/news",
        "https://www.cbssports.com/rss/headlines/nba/",
    ],
)

INJURY_SOURCES = _env_csv(
    "INJURY_SOURCES",
    [
        "https://www.rotowire.com/rss/news.php?sport=NBA",
    ],
)


# MLOps (Phase 5)
MLOPS_ACCURACY_THRESHOLD = float(os.getenv("MLOPS_ACCURACY_THRESHOLD", "0.55"))
MLOPS_MAX_BRIER = float(os.getenv("MLOPS_MAX_BRIER", "0.25"))
MLOPS_NEW_LABEL_MIN = int(os.getenv("MLOPS_NEW_LABEL_MIN", "40"))
MLOPS_FRESHNESS_DAYS = int(os.getenv("MLOPS_FRESHNESS_DAYS", "2"))

# ==========================================
# 💡 INTERVIEW ANGLE:
# "I centralized configuration into a single source of truth. 
# This makes the pipeline environment-agnostic and easy to 
# swap between development, testing, and production."
# ==========================================
