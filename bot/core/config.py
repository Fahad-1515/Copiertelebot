import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    _raw = os.getenv("ADMIN_LOG_GROUP_ID")
    ADMIN_LOG_GROUP_ID = int(_raw) if _raw and _raw.lstrip("-").isdigit() else _raw
    
    MAX_RETRIES = 3
    DEFAULT_DELAY = 1.0
    PROGRESS_UPDATE_INTERVAL = 5
    ADMIN_UPDATE_INTERVAL = 10
    
    QUEUE_MAXSIZE = 50
    BATCH_SIZE = 100