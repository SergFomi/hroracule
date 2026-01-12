import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List
from config import config

logger = logging.getLogger(__name__)

class FunnelConfig:
    def __init__(self):
        self.messages = {}
        self.funnel_stages = []
        self.settings = {}
        self._load_config()
    
    def _load_config(self):
        """Load funnel configuration from YAML files"""
        try:
            # Load messages
            messages_path = Path(config.CONFIG_DIR) / 'messages.yml'
            with open(messages_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.messages = data.get('messages', {})
            
            logger.info(f"Loaded {len(self.messages)} message templates")
            
            # Load funnel stages
            funnel_path = Path(config.CONFIG_DIR) / 'funnel.yml'
            with open(funnel_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.funnel_stages = data.get('funnel', [])
                self.settings = data.get('settings', {})
            
            logger.info(f"Loaded {len(self.funnel_stages)} funnel stages")
            logger.info(f"Funnel settings: {self.settings}")
            
        except Exception as e:
            logger.error(f"Error loading funnel config: {e}", exc_info=True)
            raise
    
    def get_message(self, key: str) -> Dict[str, Any]:
        """Get message template by key"""
        message = self.messages.get(key)
        if not message:
            logger.warning(f"Message template '{key}' not found")
        return message or {}
    
    def get_funnel_stages(self) -> List[Dict[str, Any]]:
        """Get all funnel stages"""
        return self.funnel_stages
    
    def get_stage_by_name(self, stage_name: str) -> Dict[str, Any]:
        """Get funnel stage by name"""
        for stage in self.funnel_stages:
            if stage.get('stage') == stage_name:
                return stage
        logger.warning(f"Funnel stage '{stage_name}' not found")
        return {}
    
    def reload(self):
        """Reload configuration from files"""
        logger.info("Reloading funnel configuration...")
        self._load_config()
        logger.info("Funnel configuration reloaded")

funnel_config = FunnelConfig()
