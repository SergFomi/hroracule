import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from sheets_service import sheets_service
from message_sender import MessageSender
from funnel_loader import funnel_config

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "webinar_yes")
async def callback_webinar_yes(callback: CallbackQuery):
    """Handle webinar YES button"""
    user_id = callback.from_user.id
    
    logger.info(f"User {user_id} clicked YES for webinar")
    
    try:
        # Update user stage
        await db.update_user_stage(user_id, 'webinar_registered')
        await db.add_event(user_id, 'webinar_yes', 'User accepted webinar invite')
        
        # Update in Google Sheets
        await sheets_service.update_user_stage(user_id, 'webinar_registered')
        
        # Send webinar link
        message_sender = MessageSender(callback.bot)
        webinar_link_msg = funnel_config.get_message('webinar_link')
        
        if webinar_link_msg:
            await callback.message.answer(webinar_link_msg.get('text', ''))
        
        # Answer callback to remove loading state
        await callback.answer("Отлично! Жду тебя на вебинаре 🎉")
        
        logger.info(f"Webinar link sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling webinar YES for user {user_id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "webinar_no")
async def callback_webinar_no(callback: CallbackQuery):
    """Handle webinar NO button"""
    user_id = callback.from_user.id
    
    logger.info(f"User {user_id} clicked NO for webinar")
    
    try:
        # Update user stage
        await db.update_user_stage(user_id, 'webinar_declined')
        await db.add_event(user_id, 'webinar_no', 'User declined webinar invite')
        
        # Update in Google Sheets
        await sheets_service.update_user_stage(user_id, 'webinar_declined')
        
        # Send decline message
        message_sender = MessageSender(callback.bot)
        decline_msg = funnel_config.get_message('webinar_decline')
        
        if decline_msg:
            await callback.message.answer(decline_msg.get('text', ''))
        
        # Answer callback
        await callback.answer()
        
        logger.info(f"Webinar declined for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling webinar NO for user {user_id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query()
async def callback_unknown(callback: CallbackQuery):
    """Handle unknown callbacks"""
    logger.warning(f"Unknown callback from user {callback.from_user.id}: {callback.data}")
    await callback.answer()
