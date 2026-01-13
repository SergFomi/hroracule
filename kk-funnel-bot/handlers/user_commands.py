import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database import db
from sheets_service import sheets_service

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("был_на_вебинаре", "webinar_attended"))
async def cmd_webinar_attended(message: Message):
    """Mark user as attended webinar"""
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} marked webinar as attended")
    
    try:
        # Update flag in database
        success = await db.update_user_flag(user_id, 'attended_webinar', 1)
        
        if success:
            # Log event
            await db.add_event(user_id, 'webinar_attended', 'User attended webinar')
            
            # Sync to Google Sheets
            user = await db.get_user(user_id)
            if user:
                await sheets_service.sync_user(user)
            
            await message.answer(
                "✅ Отлично! Отметил что ты был на вебинаре.\n\n"
                "Рад что ты был с нами! 🎉"
            )
            logger.info(f"User {user_id} marked as attended webinar")
        else:
            await message.answer("❌ Ошибка обновления. Попробуй позже.")
    
    except Exception as e:
        logger.error(f"Error marking webinar attended for user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуй позже.")

@router.message(Command("была_консультация", "had_consultation"))
async def cmd_had_consultation(message: Message):
    """Mark user as had consultation"""
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} marked consultation as completed")
    
    try:
        # Update flag in database
        success = await db.update_user_flag(user_id, 'had_consultation', 1)
        
        if success:
            # Log event
            await db.add_event(user_id, 'consultation_completed', 'User had consultation')
            
            # Sync to Google Sheets
            user = await db.get_user(user_id)
            if user:
                await sheets_service.sync_user(user)
            
            await message.answer(
                "✅ Отлично! Отметил что у тебя была консультация.\n\n"
                "Надеюсь она была полезной! 💪"
            )
            logger.info(f"User {user_id} marked as had consultation")
        else:
            await message.answer("❌ Ошибка обновления. Попробуй позже.")
    
    except Exception as e:
        logger.error(f"Error marking consultation for user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуй позже.")

@router.message(Command("начал_искать_работу", "started_job_search"))
async def cmd_started_job_search(message: Message):
    """Mark user as started job search"""
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} marked job search as started")
    
    try:
        # Update flag in database
        success = await db.update_user_flag(user_id, 'started_job_search', 1)
        
        if success:
            # Log event
            await db.add_event(user_id, 'job_search_started', 'User started job search')
            
            # Sync to Google Sheets
            user = await db.get_user(user_id)
            if user:
                await sheets_service.sync_user(user)
            
            await message.answer(
                "✅ Отлично! Отметил что ты начал искать работу.\n\n"
                "Удачи в поисках! Если нужна помощь - пиши! 🚀"
            )
            logger.info(f"User {user_id} marked as started job search")
        else:
            await message.answer("❌ Ошибка обновления. Попробуй позже.")
    
    except Exception as e:
        logger.error(f"Error marking job search for user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуй позже.")

@router.message(Command("нашел_работу", "got_job"))
async def cmd_got_job(message: Message):
    """Mark user as got a job"""
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} marked job as found")
    
    try:
        # Update flag in database
        success = await db.update_user_flag(user_id, 'got_job', 1)
        
        if success:
            # Log event
            await db.add_event(user_id, 'job_found', 'User found a job')
            
            # Sync to Google Sheets
            user = await db.get_user(user_id)
            if user:
                await sheets_service.sync_user(user)
            
            await message.answer(
                "🎉 ПОЗДРАВЛЯЮ! Ты нашел работу!\n\n"
                "Это отличная новость! Желаю успехов на новом месте! 🚀\n\n"
                "Буду рад если поделишься своим опытом с другими участниками! 💪"
            )
            logger.info(f"User {user_id} marked as got a job")
        else:
            await message.answer("❌ Ошибка обновления. Попробуй позже.")
    
    except Exception as e:
        logger.error(f"Error marking job found for user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуй позже.")

@router.message(Command("мой_статус", "my_status"))
async def cmd_my_status(message: Message):
    """Show user's current status and flags"""
    user_id = message.from_user.id
    
    try:
        user = await db.get_user(user_id)
        
        if not user:
            await message.answer("❌ Не могу найти твои данные")
            return
        
        status_text = "📊 <b>Твой статус:</b>\n\n"
        
        # Webinar
        if user.get('attended_webinar'):
            status_text += "✅ Был на вебинаре\n"
        else:
            status_text += "⬜️ Не был на вебинаре\n"
        
        # Consultation
        if user.get('had_consultation'):
            status_text += "✅ Была консультация\n"
        else:
            status_text += "⬜️ Не было консультации\n"
        
        # Job search
        if user.get('started_job_search'):
            status_text += "✅ Начал искать работу\n"
        else:
            status_text += "⬜️ Еще не начал поиск\n"
        
        # Got job
        if user.get('got_job'):
            status_text += "✅ Нашел работу! 🎉\n"
        else:
            status_text += "⬜️ Еще в поиске\n"
        
        status_text += f"\n📍 Текущий этап: {user.get('current_stage', 'unknown')}\n"
        status_text += f"📅 Регистрация: {user.get('created_at', 'unknown')[:10]}\n"
        
        await message.answer(status_text, parse_mode='HTML')
        logger.info(f"Status shown to user {user_id}")
    
    except Exception as e:
        logger.error(f"Error showing status to user {user_id}: {e}", exc_info=True)
        await message.answer("❌ Ошибка получения статуса")
