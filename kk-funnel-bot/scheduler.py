import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

from database import db
from sheets_service import sheets_service
from funnel_loader import funnel_config
from message_sender import MessageSender

logger = logging.getLogger(__name__)

class FunnelScheduler:
    def __init__(self, bot: 'Bot'):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.message_sender = MessageSender(bot)
        logger.info("Funnel scheduler initialized")
    
    def start(self):
        """Start the scheduler"""
        # Check for pending messages every minute
        self.scheduler.add_job(
            self.process_pending_messages,
            IntervalTrigger(minutes=1),
            id='process_pending_messages',
            replace_existing=True
        )
        
        # Sync database to Google Sheets every 5 minutes
        self.scheduler.add_job(
            self.sync_to_sheets,
            IntervalTrigger(minutes=5),
            id='sync_to_sheets',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    async def schedule_funnel_for_user(self, user_id: int):
        """Schedule all funnel messages for a new user"""
        logger.info(f"Scheduling funnel for user {user_id}")
        
        try:
            funnel_stages = funnel_config.get_funnel_stages()
            now = datetime.utcnow()
            
            for stage in funnel_stages:
                delay_seconds = stage.get('delay_seconds', 0)
                scheduled_at = now + timedelta(seconds=delay_seconds)
                
                await db.schedule_message(
                    user_id=user_id,
                    stage=stage['stage'],
                    scheduled_at=scheduled_at
                )
                
                logger.info(
                    f"Scheduled stage '{stage['stage']}' for user {user_id} "
                    f"at {scheduled_at} (delay: {delay_seconds}s)"
                )
            
            logger.info(f"Funnel scheduled successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error scheduling funnel for user {user_id}: {e}", exc_info=True)
    
    async def process_pending_messages(self):
        """Process all pending scheduled messages"""
        try:
            pending = await db.get_pending_messages()
            
            if not pending:
                return
            
            logger.info(f"Processing {len(pending)} pending messages")
            
            for msg in pending:
                try:
                    # Get user and check if active
                    user = await db.get_user(msg['user_id'])
                    
                    if not user or not user.get('is_active'):
                        logger.info(f"Skipping message {msg['id']} - user {msg['user_id']} inactive")
                        await db.mark_message_sent(msg['id'])
                        continue
                    
                    # Check retry limit
                    max_retries = funnel_config.settings.get('max_retries', 3)
                    if msg['retry_count'] >= max_retries:
                        logger.warning(
                            f"Message {msg['id']} exceeded retry limit ({max_retries}), "
                            f"marking as sent"
                        )
                        await db.mark_message_sent(msg['id'])
                        continue
                    
                    # Send message
                    success = await self.message_sender.send_funnel_message(
                        user_id=msg['user_id'],
                        stage=msg['stage']
                    )
                    
                    if success:
                        await db.mark_message_sent(msg['id'])
                        await db.update_user_stage(msg['user_id'], msg['stage'])
                        
                        # Sync to Google Sheets
                        await sheets_service.update_user_stage(msg['user_id'], msg['stage'])
                        
                        logger.info(f"Message {msg['id']} sent successfully to user {msg['user_id']}")
                    else:
                        await db.increment_retry_count(msg['id'])
                        logger.warning(f"Failed to send message {msg['id']}, will retry")
                    
                except Exception as e:
                    logger.error(
                        f"Error processing message {msg['id']} for user {msg['user_id']}: {e}",
                        exc_info=True
                    )
                    await db.increment_retry_count(msg['id'])
            
        except Exception as e:
            logger.error(f"Error in process_pending_messages: {e}", exc_info=True)
    
    async def sync_to_sheets(self):
        """Sync all users to Google Sheets"""
        try:
            logger.info("Starting periodic sync to Google Sheets")
            users = await db.get_all_users()
            
            if users:
                synced = await sheets_service.batch_sync_users(users)
                logger.info(f"Synced {synced}/{len(users)} users to Google Sheets")
            
        except Exception as e:
            logger.error(f"Error syncing to Google Sheets: {e}", exc_info=True)

scheduler_instance = None

def get_scheduler(bot: 'Bot') -> FunnelScheduler:
    """Get or create scheduler instance"""
    global scheduler_instance
    if scheduler_instance is None:
        scheduler_instance = FunnelScheduler(bot)
    return scheduler_instance
