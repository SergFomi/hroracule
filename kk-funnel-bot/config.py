import os
import json
import logging
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

class Config:
    """Application configuration"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('KK_TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('KK_TELEGRAM_CHANNEL_ID')
    
    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv('KK_GOOGLE_SHEETS_CREDENTIALS')
    GOOGLE_SHEET_ID = os.getenv('KK_GOOGLE_SHEET_ID')
    
    # Parse Google credentials immediately
    GOOGLE_CREDENTIALS = None
    if GOOGLE_SHEETS_CREDENTIALS_JSON:
        try:
            GOOGLE_CREDENTIALS = json.loads(GOOGLE_SHEETS_CREDENTIALS_JSON)
            logger.info("Google credentials parsed successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Google credentials: {e}")
    
    # Admin
    ADMIN_USER_IDS_STR = os.getenv('KK_ADMIN_USER_IDS', '')
    ADMIN_USER_IDS: List[int] = [
        int(uid.strip()) for uid in ADMIN_USER_IDS_STR.split(',') if uid.strip()
    ]
    
    # App
    UPTIME_ROBOT_MONITOR = os.getenv('KK_UPTIME_ROBOT_MONITOR', 'false').lower() == 'true'
    
    # Database
    DATABASE_PATH = 'bot_data.db'
    
    # Paths
    CONFIG_DIR = 'config'
    MEDIA_DIR = 'media'
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("KK_TELEGRAM_BOT_TOKEN is not set")
            logger.error("Missing KK_TELEGRAM_BOT_TOKEN")
        
        if not cls.GOOGLE_SHEETS_CREDENTIALS_JSON:
            errors.append("KK_GOOGLE_SHEETS_CREDENTIALS is not set")
            logger.error("Missing KK_GOOGLE_SHEETS_CREDENTIALS")
        
        if not cls.GOOGLE_SHEET_ID:
            errors.append("KK_GOOGLE_SHEET_ID is not set")
            logger.error("Missing KK_GOOGLE_SHEET_ID")
        
        if not cls.GOOGLE_CREDENTIALS:
            errors.append("Failed to parse KK_GOOGLE_SHEETS_CREDENTIALS JSON")
            logger.error("Google credentials parsing failed")
        
        if errors:
            logger.critical(f"Configuration errors: {', '.join(errors)}")
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        logger.info("Configuration validated successfully")
        logger.info(f"Admin users: {cls.ADMIN_USER_IDS}")
        logger.info(f"Uptime monitor: {cls.UPTIME_ROBOT_MONITOR}")

config = Config()
