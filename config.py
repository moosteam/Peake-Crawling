import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true"

HEADLESS_MODE = os.getenv("HEADLESS_MODE", "True").lower() == "true"
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "10"))
DEFAULT_MAX_WORKERS = int(os.getenv("DEFAULT_MAX_WORKERS", "4"))

CHANNELS_FILE = os.getenv("CHANNELS_FILE", str(DATA_DIR / "channels.json"))