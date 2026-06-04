import logging
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config.settings import Config
except ImportError:
    # Fallback config if settings not available
    class Config:
        LOG_LEVEL = "INFO"
        LOGS_DIR = Path(__file__).parent.parent / "logs"

def setup_logger(name: str) -> logging.Logger:
    """Setup logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

    # Prevent duplicate handlers when setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - create log directory if it doesn't exist
    log_dir = Config.LOGS_DIR / name.split('_')[0] if '_' in name else Config.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger