import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from config import config

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in config.ADMIN_USER_IDS

@router.message(F.text & ~F.text.startswith('/'))
async def handle_user_message(message: Message):
    """Handle incoming messages from users"""
    user_id = message.from_user.id
    
    # If message is a reply from admin - forward to original user
    if is_admin(user_id) and message.reply_to_message:
        await handle_admin_reply(message)
        return
    
    # If regular user message - forward to admin
    if not is_admin(user_id):
        await forward_to_admin(message)
        return

async def forward_to_admin(message: Message):
    """Forward user message to admin"""
    user = message.from_user
    user_id = user.id
    
    try:
        # Log the message
        await db.add_event(user_id, 'user_message', message.text[:100] if message.text else 'media')
        
        # Format message for admin
        user_info = (
            f"📨 <b>Новое сообщение от пользователя</b>\n\n"
            f"👤 {user.first_name or 'Unknown'}"
        )
        
        if user.last_name:
            user_info += f" {user.last_name}"
        
        if user.username:
            user_info += f" (@{user.username})"
        
        user_info += f"\n🆔 ID: <code>{user_id}</code>\n"
        user_info += f"🔗 <a href='tg://user?id={user_id}'>Профиль</a>\n\n"
        
        # Get user's current stage
        user_data = await db.get_user(user_id)
        if user_data:
            user_info += f"📍 Этап: {user_data.get('current_stage', 'unknown')}\n\n"
        
        user_info += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Send to all admins
        for admin_id in config.ADMIN_USER_IDS:
            try:
                # Send user info
                await message.bot.send_message(admin_id, user_info, parse_mode='HTML')
                
                # Forward the actual message
                await message.forward(admin_id)
                
                # Send instruction
                instruction = (
                    "💡 <i>Чтобы ответить пользователю, сделай Reply на его сообщение выше</i>"
                )
                await message.bot.send_message(admin_id, instruction, parse_mode='HTML')
                
                logger.info(f"Forwarded message from user {user_id} to admin {admin_id}")
                
            except Exception as e:
                logger.error(f"Failed to forward to admin {admin_id}: {e}", exc_info=True)
        
        # Confirm to user
        await message.answer(
            "✅ Сообщение отправлено! Я свяжусь с тобой в ближайшее время."
        )
        
    except Exception as e:
        logger.error(f"Error forwarding message from user {user_id}: {e}", exc_info=True)

async def handle_admin_reply(message: Message):
    """Handle admin reply to user message"""
    try:
        # Extract user_id from the replied message
        replied_msg = message.reply_to_message
        
        # Check if replied message is forwarded from a user
        if replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id
        elif replied_msg.forward_sender_name:
            # User has privacy settings - can't reply
            await message.answer(
                "❌ Не могу ответить этому пользователю - у него скрыта пересылка сообщений.\n"
                "Попроси его написать тебе напрямую."
            )
            return
        else:
            # Try to extract from text if it's our formatted message
            # Look for ID: <code>123456789</code>
            import re
            text = replied_msg.text or replied_msg.caption or ""
            match = re.search(r'ID: <code>(\d+)</code>', text)
            
            if not match:
                await message.answer(
                    "❌ Не могу определить ID пользователя. "
                    "Убедись что делаешь Reply на пересланное сообщение."
                )
                return
            
            target_user_id = int(match.group(1))
        
        # Send reply to user
        if message.text:
            await message.bot.send_message(target_user_id, message.text)
        elif message.photo:
            await message.bot.send_photo(
                target_user_id, 
                message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.document:
            await message.bot.send_document(
                target_user_id,
                message.document.file_id,
                caption=message.caption
            )
        elif message.video:
            await message.bot.send_video(
                target_user_id,
                message.video.file_id,
                caption=message.caption
            )
        elif message.voice:
            await message.bot.send_voice(
                target_user_id,
                message.voice.file_id,
                caption=message.caption
            )
        else:
            # Try to copy the message as is
            await message.copy_to(target_user_id)
        
        # Log the reply
        await db.add_event(target_user_id, 'admin_reply', 'Admin replied to user')
        
        # Confirm to admin
        await message.answer("✅ Ответ отправлен пользователю!")
        
        logger.info(f"Admin {message.from_user.id} replied to user {target_user_id}")
        
    except Exception as e:
        logger.error(f"Error handling admin reply: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка отправки: {e}")
