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
            "/help - Это сообщение\n"
        )
    else:
        help_text = (
            "👋 Привет! Я бот-помощник для поиска удаленной работы.\n\n"
            "Просто следуй инструкциям, которые я буду присылать! 🚀"
        )
    
    await message.answer(help_text, parse_mode='HTML')
    logger.info(f"Help sent to user {user_id}")
