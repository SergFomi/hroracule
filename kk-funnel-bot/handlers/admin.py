import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database import db
from config import config
from funnel_loader import funnel_config

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in config.ADMIN_USER_IDS

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show bot statistics (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        logger.warning(f"Non-admin user {user_id} tried to access /stats")
        return
    
    logger.info(f"Admin {user_id} requested stats")
    
    try:
        stats = await db.get_stats()
        
        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"✅ Активных: {stats['active_users']}\n"
            f"📨 Отправлено сообщений: {stats['messages_sent']}\n"
        )
        
        await message.answer(stats_text, parse_mode='HTML')
        logger.info(f"Stats sent to admin {user_id}")
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        await message.answer("Ошибка получения статистики")

@router.message(Command("reload"))
async def cmd_reload(message: Message):
    """Reload funnel configuration (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        logger.warning(f"Non-admin user {user_id} tried to access /reload")
        return
    
    logger.info(f"Admin {user_id} requested config reload")
    
    try:
        funnel_config.reload()
        await message.answer("✅ Конфигурация воронки перезагружена")
        logger.info(f"Config reloaded by admin {user_id}")
        
    except Exception as e:
        logger.error(f"Error reloading config: {e}", exc_info=True)
        await message.answer("❌ Ошибка перезагрузки конфигурации")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Broadcast message to all active users (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        logger.warning(f"Non-admin user {user_id} tried to access /broadcast")
        return
    
    logger.info(f"Admin {user_id} initiated broadcast")
    
    # Check if there's a message to broadcast
    if not message.reply_to_message:
        await message.answer(
            "ℹ️ Ответь на сообщение командой /broadcast чтобы разослать его всем пользователям"
        )
        return
    
    try:
        users = await db.get_all_users()
        active_users = [u for u in users if u.get('is_active', False)]
        
        success_count = 0
        fail_count = 0
        
        status_msg = await message.answer(
            f"📤 Начинаю рассылку {len(active_users)} пользователям..."
        )
        
        for user in active_users:
            try:
                await message.reply_to_message.copy_to(user['user_id'])
                success_count += 1
                
                # Update status every 10 users
                if success_count % 10 == 0:
                    await status_msg.edit_text(
                        f"📤 Отправлено: {success_count}/{len(active_users)}"
                    )
                
            except Exception as e:
                logger.error(f"Failed to broadcast to user {user['user_id']}: {e}")
                fail_count += 1
        
        await status_msg.edit_text(
            f"✅ Рассылка завершена\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {fail_count}"
        )
        
        logger.info(f"Broadcast completed: {success_count} success, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in broadcast: {e}", exc_info=True)
        await message.answer("❌ Ошибка рассылки")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message"""
    user_id = message.from_user.id
    
    if is_admin(user_id):
        help_text = (
            "🤖 <b>Команды администратора:</b>\n\n"
            "/stats - Статистика бота\n"
            "/reload - Перезагрузить конфигурацию\n"
            "/broadcast - Рассылка (ответь на сообщение)\n"
            "/send_webinar - Отправить приглашение на вебинар всем активным\n"
            "/send_followup - Отправить follow-up всем активным\n"
            "/help - Это сообщение\n\n"
            "📥 <b>Входящие сообщения:</b>\n"
            "Все сообщения от пользователей пересылаются тебе.\n"
            "Чтобы ответить - сделай Reply на сообщение пользователя.\n"
        )
    else:
        help_text = (
            "👋 Привет! Я бот-помощник для поиска удаленной работы.\n\n"
            "Просто следуй инструкциям, которые я буду присылать! 🚀\n\n"
            "Если у тебя есть вопросы - просто напиши мне, и я передам их создателю."
        )
    
    await message.answer(help_text, parse_mode='HTML')
    logger.info(f"Help sent to user {user_id}")

@router.message(Command("send_webinar"))
async def cmd_send_webinar(message: Message):
    """Send webinar invite to all active users (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        logger.warning(f"Non-admin user {user_id} tried to access /send_webinar")
        return
    
    logger.info(f"Admin {user_id} initiated webinar broadcast")
    
    try:
        from message_sender import MessageSender
        
        # Get all active users who completed at least 'resume' stage
        users = await db.get_all_users()
        target_users = [
            u for u in users 
            if u.get('is_active', False) and 
            u.get('current_stage') in ['resume', 'webinar_invite', 'webinar_registered', 'webinar_declined', 'followup_1']
        ]
        
        if not target_users:
            await message.answer("❌ Нет подходящих пользователей для рассылки")
            return
        
        success_count = 0
        fail_count = 0
        
        status_msg = await message.answer(
            f"📤 Начинаю рассылку вебинара {len(target_users)} пользователям..."
        )
        
        message_sender = MessageSender(message.bot)
        
        for user in target_users:
            try:
                # Send webinar invite
                success = await message_sender.send_funnel_message(
                    user_id=user['user_id'],
                    stage='webinar_invite'
                )
                
                if success:
                    success_count += 1
                    # Update stage
                    await db.update_user_stage(user['user_id'], 'webinar_invite')
                else:
                    fail_count += 1
                
                # Update status every 10 users
                if (success_count + fail_count) % 10 == 0:
                    await status_msg.edit_text(
                        f"📤 Отправлено: {success_count}/{len(target_users)}\n"
                        f"❌ Ошибок: {fail_count}"
                    )
                
            except Exception as e:
                logger.error(f"Failed to send webinar to user {user['user_id']}: {e}")
                fail_count += 1
        
        await status_msg.edit_text(
            f"✅ Рассылка вебинара завершена\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {fail_count}"
        )
        
        logger.info(f"Webinar broadcast completed: {success_count} success, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in webinar broadcast: {e}", exc_info=True)
        await message.answer("❌ Ошибка рассылки вебинара")

@router.message(Command("send_followup"))
async def cmd_send_followup(message: Message):
    """Send follow-up message to all active users (admin only)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        logger.warning(f"Non-admin user {user_id} tried to access /send_followup")
        return
    
    logger.info(f"Admin {user_id} initiated follow-up broadcast")
    
    try:
        from message_sender import MessageSender
        
        # Get all active users
        users = await db.get_all_users()
        target_users = [u for u in users if u.get('is_active', False)]
        
        if not target_users:
            await message.answer("❌ Нет активных пользователей")
            return
        
        success_count = 0
        fail_count = 0
        
        status_msg = await message.answer(
            f"📤 Начинаю рассылку follow-up {len(target_users)} пользователям..."
        )
        
        message_sender = MessageSender(message.bot)
        
        for user in target_users:
            try:
                # Send follow-up
                success = await message_sender.send_funnel_message(
                    user_id=user['user_id'],
                    stage='followup_1'
                )
                
                if success:
                    success_count += 1
                    await db.update_user_stage(user['user_id'], 'followup_1')
                else:
                    fail_count += 1
                
                # Update status every 10 users
                if (success_count + fail_count) % 10 == 0:
                    await status_msg.edit_text(
                        f"📤 Отправлено: {success_count}/{len(target_users)}\n"
                        f"❌ Ошибок: {fail_count}"
                    )
                
            except Exception as e:
                logger.error(f"Failed to send follow-up to user {user['user_id']}: {e}")
                fail_count += 1
        
        await status_msg.edit_text(
            f"✅ Рассылка follow-up завершена\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {fail_count}"
        )
        
        logger.info(f"Follow-up broadcast completed: {success_count} success, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in follow-up broadcast: {e}", exc_info=True)
        await message.answer("❌ Ошибка рассылки follow-up")
