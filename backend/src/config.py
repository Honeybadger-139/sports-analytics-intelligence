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

# ==========================================
# 💡 INTERVIEW ANGLE:
# "I centralized configuration into a single source of truth. 
# This makes the pipeline environment-agnostic and easy to 
# swap between development, testing, and production."
# ==========================================
