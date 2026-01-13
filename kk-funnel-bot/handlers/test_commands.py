import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from database import db
from config import config

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in config.ADMIN_USER_IDS

@router.message(Command("reset_me"))
async def cmd_reset_me(message: Message):
    """Reset user data for testing (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    logger.info(f"Admin {user_id} resetting their data for testing")
    
    try:
        import aiosqlite
        from scheduler import get_scheduler
        
        # Delete scheduled messages
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute('DELETE FROM scheduled_messages WHERE user_id = ?', (user_id,))
            await conn.execute('''
                UPDATE users 
                SET attended_webinar = 0,
                    had_consultation = 0,
                    started_job_search = 0,
                    got_job = 0,
                    webinar_response = NULL,
                    current_stage = 'new'
                WHERE user_id = ?
            ''', (user_id,))
            await conn.commit()
        
        # Schedule new funnel
        scheduler = get_scheduler(message.bot)
        await scheduler.schedule_funnel_for_user(user_id)
        
        await message.answer(
            "✅ Твои данные сброшены!\n"
            "Воронка запущена заново для тестирования."
        )
        
        logger.info(f"User {user_id} data reset and funnel restarted")
        
    except Exception as e:
        logger.error(f"Error resetting user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Ошибка сброса данных")
