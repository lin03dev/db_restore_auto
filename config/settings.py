import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DUMPS_DIR = BASE_DIR / "dumps"
    LOGS_DIR = BASE_DIR / "logs"
    
    # Ensure directories exist
    DUMPS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / "backup").mkdir(exist_ok=True, parents=True)
    (LOGS_DIR / "restore").mkdir(exist_ok=True, parents=True)
    (LOGS_DIR / "error").mkdir(exist_ok=True, parents=True)
    (LOGS_DIR / "reports").mkdir(exist_ok=True, parents=True)
    
    # Local DB connection settings
    LOCAL_DB_CONFIG = {
        "host": os.getenv("LOCAL_DB_HOST", "localhost"),
        "port": os.getenv("LOCAL_DB_PORT", "5432"),
        "username": os.getenv("LOCAL_DB_USER", "postgres"),
        "password": os.getenv("LOCAL_DB_PASSWORD", "postgres")
    }
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))