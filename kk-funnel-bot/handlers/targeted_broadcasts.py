import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import config
from message_sender import MessageSender

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in config.ADMIN_USER_IDS

@router.message(Command("send_webinar"))
async def cmd_send_webinar(message: Message):
    """Send webinar invite with time (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Check if there's time info
    parts = message.text.split(maxsplit=1)
    webinar_time = parts[1] if len(parts) > 1 else None
    
    if not webinar_time:
        await message.answer(
            "ℹ️ Укажи время вебинара:\n"
            "<code>/send_webinar завтра в 19:00 МСК</code>",
            parse_mode='HTML'
        )
        return
    
    logger.info(f"Admin {user_id} sending webinar invite for: {webinar_time}")
    
    try:
        # Get users who haven't attended webinar yet
        users = await db.get_all_users()
        target_users = [
            u for u in users 
            if u.get('is_active', False) and not u.get('attended_webinar', False)
        ]
        
        if not target_users:
            await message.answer("❌ Нет подходящих пользователей")
            return
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, буду!", callback_data="webinar_yes")],
            [InlineKeyboardButton(text="Нет, спасибо", callback_data="webinar_no")]
        ])
        
        webinar_text = (
            f"🎯 Приглашаю тебя на вебинар!\n\n"
            f"⏰ Время: {webinar_time}\n\n"
            f"Разберем:\n"
            f"• Как составить резюме, которое заметят\n"
            f"• Где искать вакансии\n"
            f"• Как пройти собеседование\n\n"
            f"Участвуешь?"
        )
        
        success = 0
        fail = 0
        status_msg = await message.answer(f"📤 Отправляю {len(target_users)} пользователям...")
        
        for user in target_users:
            try:
                await message.bot.send_message(user['user_id'], webinar_text, reply_markup=keyboard)
                success += 1
                await db.update_user_stage(user['user_id'], 'webinar_invite')
                
                if success % 10 == 0:
                    await status_msg.edit_text(f"📤 Отправлено: {success}/{len(target_users)}")
            except Exception as e:
                logger.error(f"Failed to send to {user['user_id']}: {e}")
                fail += 1
        
        await status_msg.edit_text(f"✅ Готово!\nУспешно: {success}\nОшибок: {fail}")
        
    except Exception as e:
        logger.error(f"Error in send_webinar: {e}", exc_info=True)
        await message.answer("❌ Ошибка рассылки")

@router.message(Command("send_webinar_link"))
async def cmd_send_webinar_link(message: Message):
    """Send webinar link to those who said YES"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    parts = message.text.split(maxsplit=1)
    webinar_link = parts[1] if len(parts) > 1 else None
    
    if not webinar_link:
        await message.answer(
            "ℹ️ Укажи ссылку:\n<code>/send_webinar_link https://zoom.us/...</code>",
            parse_mode='HTML'
        )
        return
    
    logger.info(f"Admin {user_id} sending webinar link")
    
    try:
        users = await db.get_all_users()
        target_users = [u for u in users if u.get('webinar_response') == 'yes']
        
        if not target_users:
            await message.answer("❌ Нет пользователей, которые записались")
            return
        
        link_text = f"🔗 Ссылка на вебинар:\n\n{webinar_link}\n\nДо встречи! 👋"
        
        success = 0
        status_msg = await message.answer(f"📤 Отправляю {len(target_users)} пользователям...")
        
        for user in target_users:
            try:
                await message.bot.send_message(user['user_id'], link_text)
                success += 1
            except Exception as e:
                logger.error(f"Failed to send link to {user['user_id']}: {e}")
        
        await status_msg.edit_text(f"✅ Ссылки отправлены: {success}/{len(target_users)}")
        
    except Exception as e:
        logger.error(f"Error sending links: {e}", exc_info=True)
        await message.answer("❌ Ошибка отправки")

@router.message(Command("broadcast_webinar"))
async def cmd_broadcast_webinar(message: Message):
    """Broadcast to users who attended webinar"""
    user_id = message.from_user.id
    
    if not is_admin(user_id) or not message.reply_to_message:
        return
    
    await _targeted_broadcast(
        message, 
        filter_func=lambda u: u.get('attended_webinar', False),
        label="кто был на вебинаре"
    )

@router.message(Command("broadcast_consultation"))
async def cmd_broadcast_consultation(message: Message):
    """Broadcast to users who had consultation"""
    user_id = message.from_user.id
    
    if not is_admin(user_id) or not message.reply_to_message:
        return
    
    await _targeted_broadcast(
        message, 
        filter_func=lambda u: u.get('had_consultation', False),
        label="у кого была консультация"
    )

@router.message(Command("broadcast_searching"))
async def cmd_broadcast_searching(message: Message):
    """Broadcast to users who started job search"""
    user_id = message.from_user.id
    
    if not is_admin(user_id) or not message.reply_to_message:
        return
    
    await _targeted_broadcast(
        message, 
        filter_func=lambda u: u.get('started_job_search', False),
        label="кто ищет работу"
    )

@router.message(Command("broadcast_found"))
async def cmd_broadcast_found(message: Message):
    """Broadcast to users who got a job"""
    user_id = message.from_user.id
    
    if not is_admin(user_id) or not message.reply_to_message:
        return
    
    await _targeted_broadcast(
        message, 
        filter_func=lambda u: u.get('got_job', False),
        label="кто нашёл работу"
    )

async def _targeted_broadcast(message: Message, filter_func, label: str):
    """Helper function for targeted broadcasts"""
    try:
        users = await db.get_all_users()
        target_users = [u for u in users if u.get('is_active', False) and filter_func(u)]
        
        if not target_users:
            await message.answer(f"❌ Нет пользователей ({label})")
            return
        
        success = 0
        fail = 0
        
        status_msg = await message.answer(
            f"📤 Рассылка для {len(target_users)} пользователей ({label})..."
        )
        
        for user in target_users:
            try:
                await message.reply_to_message.copy_to(user['user_id'])
                success += 1
                
                if success % 10 == 0:
                    await status_msg.edit_text(f"📤 Отправлено: {success}/{len(target_users)}")
            except Exception as e:
                logger.error(f"Failed to broadcast to {user['user_id']}: {e}")
                fail += 1
        
        await status_msg.edit_text(
            f"✅ Рассылка завершена\nУспешно: {success}\nОшибок: {fail}"
        )
        
        logger.info(f"Targeted broadcast ({label}): {success} success, {fail} failed")
        
    except Exception as e:
        logger.error(f"Error in targeted broadcast: {e}", exc_info=True)
        await message.answer("❌ Ошибка рассылки")
