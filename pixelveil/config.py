"""Configuration, directory setup, camera database, and session store."""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
CAMERAS_DB_PATH = os.path.join(BASE_DIR, "cameras_db.json")
CONFIG_PATH = os.path.join(BASE_DIR, "pixelveil_config.txt")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

with open(CAMERAS_DB_PATH, "r", encoding="utf-8") as f:
    CAMERAS_DB = json.load(f)

# In-memory session store: session_id -> {original_path, current_path, original_meta, current_meta}
SESSIONS = {}

# Load Groq API key from environment variable or pixelveil_config.txt
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY and os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as _cf:
        for _line in _cf:
            _line = _line.strip()
            if _line.startswith("GROQ_API_KEY="):
                GROQ_API_KEY = _line.split("=", 1)[1].strip()
                break

if GROQ_API_KEY:
    print(f"[PixelVeil] Groq API key loaded ({GROQ_API_KEY[:8]}...)")
else:
    print("[PixelVeil] WARNING: No Groq API key found. AI Agent will be disabled.")
