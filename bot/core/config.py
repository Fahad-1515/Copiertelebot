import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    _raw = os.getenv("ADMIN_LOG_GROUP_ID")
    ADMIN_LOG_GROUP_ID = int(_raw) if _raw.lstrip("-").isdigit() else _raw
    
    MAX_RETRIES = 3
    DEFAULT_DELAY = 3.0
    PROGRESS_UPDATE_INTERVAL = 5  # messages
    ADMIN_UPDATE_INTERVAL = 10    # messages