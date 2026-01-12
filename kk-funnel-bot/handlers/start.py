import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from database import db
from sheets_service import sheets_service
from scheduler import get_scheduler
from message_sender import MessageSender
from funnel_loader import funnel_config
from config import config

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command - entry point for new users"""
    user = message.from_user
    user_id = user.id
    
    logger.info(f"User {user_id} (@{user.username}) started the bot")
    
    try:
        # Extract UTM parameters from deep link if present
        utm_params = {}
        if message.text and len(message.text.split()) > 1:
            # Format: /start utm_source-utm_medium-utm_campaign
            params = message.text.split()[1]
            parts = params.split('-')
            if len(parts) >= 1:
                utm_params['utm_source'] = parts[0]
            if len(parts) >= 2:
                utm_params['utm_medium'] = parts[1]
            if len(parts) >= 3:
                utm_params['utm_campaign'] = parts[2]
            
            logger.info(f"UTM params for user {user_id}: {utm_params}")
        
        # Prepare user data
        user_data = {
            'user_id': user_id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': user.language_code,
            'is_bot': user.is_bot,
            'is_active': True,
            **utm_params
        }
        
        # Check if user exists
        existing_user = await db.get_user(user_id)
        is_new_user = existing_user is None
        
        # Add/update user in database
        await db.add_user(user_data)
        await db.add_event(user_id, 'start', 'User started bot')
        
        # Sync to Google Sheets
        await sheets_service.add_user(user_data)
        
        # Send welcome message and schedule funnel
        if is_new_user:
            logger.info(f"New user {user_id}, scheduling funnel")
            
            # Get scheduler and schedule funnel
            scheduler = get_scheduler(message.bot)
            await scheduler.schedule_funnel_for_user(user_id)
            
            # Notify admins
            message_sender = MessageSender(message.bot)
            admin_msg = funnel_config.get_message('admin').get('user_registered', '')
            if admin_msg:
                notification = admin_msg.format(
                    name=user.first_name or 'Unknown',
                    username=user.username or 'no_username'
                )
                await message_sender.send_admin_notification(notification)
        else:
            logger.info(f"Returning user {user_id}, reactivating")
            await db.update_user_stage(user_id, 'welcome')
        
        logger.info(f"User {user_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing /start for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
