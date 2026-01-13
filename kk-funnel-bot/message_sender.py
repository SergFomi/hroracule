import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from funnel_loader import funnel_config
from config import config

if TYPE_CHECKING:
    from aiogram.types import Message

logger = logging.getLogger(__name__)

class MessageSender:
    def __init__(self, bot: Bot):
        self.bot = bot
        logger.info("MessageSender initialized")
    
    def _create_webinar_keyboard(self):
        """Create inline keyboard for webinar invite"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, буду!", callback_data="webinar_yes")],
            [InlineKeyboardButton(text="Нет, спасибо", callback_data="webinar_no")]
        ])
    
    async def send_funnel_message(self, user_id: int, stage: str) -> bool:
        """Send a funnel message to user"""
        try:
            # Get stage config
            stage_config = funnel_config.get_stage_by_name(stage)
            if not stage_config:
                logger.error(f"Stage '{stage}' not found in funnel config")
                return False
            
            # Get message template
            message_key = stage_config.get('message_key')
            message_template = funnel_config.get_message(message_key)
            
            if not message_template:
                logger.error(f"Message template '{message_key}' not found")
                return False
            
            logger.info(f"Sending funnel message '{message_key}' to user {user_id}")
            
            # Handle different message types
            if message_template.get('forward_from_channel'):
                # Forward from channel
                return await self._forward_from_channel(user_id, message_template)
            
            elif message_template.get('file_path'):
                # Send file with text
                return await self._send_file_message(user_id, message_template)
            
            elif message_template.get('buttons'):
                # Send text with buttons
                return await self._send_button_message(user_id, message_template)
            
            else:
                # Send simple text message
                return await self._send_text_message(user_id, message_template)
        
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}", exc_info=True)
            return False
    
    async def _forward_from_channel(self, user_id: int, message_template: dict) -> bool:
        """Forward message from channel"""
        try:
            channel_id = config.TELEGRAM_CHANNEL_ID
            post_id = message_template.get('channel_post_id')
            
            if not channel_id or not post_id:
                logger.error("Channel ID or post ID not configured")
                return False
            
            # Send intro text if exists
            intro_text = message_template.get('text')
            if intro_text:
                await self.bot.send_message(user_id, intro_text)
            
            # Forward from channel
            await self.bot.forward_message(
                chat_id=user_id,
                from_chat_id=channel_id,
                message_id=post_id
            )
            
            logger.info(f"Forwarded message from channel to user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error forwarding from channel to user {user_id}: {e}", exc_info=True)
            return False
    
    async def _send_file_message(self, user_id: int, message_template: dict) -> bool:
        """Send message with file attachment"""
        try:
            text = message_template.get('text', '')
            file_path = Path(config.MEDIA_DIR) / message_template['file_path']
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            file = FSInputFile(file_path)
            
            # Determine file type and send
            if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                await self.bot.send_photo(user_id, file, caption=text)
            elif file_path.suffix.lower() in ['.pdf', '.doc', '.docx']:
                await self.bot.send_document(user_id, file, caption=text)
            else:
                await self.bot.send_document(user_id, file, caption=text)
            
            logger.info(f"Sent file message to user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending file message to user {user_id}: {e}", exc_info=True)
            return False
    
    async def _send_button_message(self, user_id: int, message_template: dict) -> bool:
        """Send message with inline buttons"""
        try:
            text = message_template.get('text', '')
            buttons = message_template.get('buttons', [])
            
            # Create inline keyboard
            keyboard_buttons = []
            for btn in buttons:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=btn['text'],
                        callback_data=btn['callback_data']
                    )
                ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await self.bot.send_message(user_id, text, reply_markup=keyboard)
            
            logger.info(f"Sent button message to user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending button message to user {user_id}: {e}", exc_info=True)
            return False
    
    async def _send_text_message(self, user_id: int, message_template: dict) -> bool:
        """Send simple text message"""
        try:
            text = message_template.get('text', '')
            
            await self.bot.send_message(user_id, text)
            
            logger.info(f"Sent text message to user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending text message to user {user_id}: {e}", exc_info=True)
            return False
    
    async def send_admin_notification(self, text: str) -> bool:
        """Send notification to admin users"""
        try:
            for admin_id in config.ADMIN_USER_IDS:
                try:
                    await self.bot.send_message(admin_id, text)
                    logger.info(f"Sent admin notification to {admin_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to admin {admin_id}: {e}")
            return True
        except Exception as e:
            logger.error(f"Error sending admin notifications: {e}", exc_info=True)
            return False
