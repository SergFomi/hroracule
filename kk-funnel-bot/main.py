import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from database import db
from scheduler import get_scheduler

# Import handlers
from handlers import start, callbacks, admin

logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Register routers
dp.include_router(start.router)
dp.include_router(callbacks.router)
dp.include_router(admin.router)

async def health_check(request):
    """Health check endpoint for UptimeRobot"""
    return web.Response(text="OK", status=200)

async def create_web_app():
    """Create web application for health checks"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    return app

async def on_startup():
    """Actions on bot startup"""
    logger.info("=" * 50)
    logger.info("Bot starting up...")
    logger.info("=" * 50)
    
    # Validate configuration
    config.validate()
    
    # Initialize database
    await db.init_db()
    logger.info("Database initialized")
    
    # Start scheduler
    scheduler = get_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")
    
    # Check for missed scheduled messages (in case bot was down)
    logger.info("Checking for pending messages after restart...")
    pending = await db.get_pending_messages()
    if pending:
        logger.info(f"Found {len(pending)} pending messages, will process them")
    
    logger.info("=" * 50)
    logger.info("Bot is ready!")
    logger.info("=" * 50)

async def on_shutdown():
    """Actions on bot shutdown"""
    logger.info("=" * 50)
    logger.info("Bot shutting down...")
    logger.info("=" * 50)
    
    # Stop scheduler
    scheduler = get_scheduler(bot)
    scheduler.stop()
    logger.info("Scheduler stopped")
    
    # Close bot session
    await bot.session.close()
    logger.info("Bot session closed")
    
    logger.info("=" * 50)
    logger.info("Bot shutdown complete")
    logger.info("=" * 50)

async def main():
    """Main function"""
    try:
        # Run startup actions
        await on_startup()
        
        # Create web app for health checks
        web_app = await create_web_app()
        runner = web.AppRunner(web_app)
        await runner.setup()
        
        # Start web server on port 8080 (Render default)
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        logger.info("Health check server started on port 8080")
        
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.critical(f"Critical error in main: {e}", exc_info=True)
        raise
    finally:
        await on_shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
