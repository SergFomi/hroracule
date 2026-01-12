import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        logger.info(f"Database initialized at {self.db_path}")
    
    async def init_db(self):
        """Initialize database tables"""
        logger.info("Initializing database tables...")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    language_code TEXT,
                    is_bot INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    utm_source TEXT,
                    utm_medium TEXT,
                    utm_campaign TEXT,
                    current_stage TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_type TEXT,
                    event_data TEXT,
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    stage TEXT,
                    scheduled_at TEXT,
                    sent INTEGER DEFAULT 0,
                    sent_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.commit()
        logger.info("Database tables initialized successfully")
    
    async def add_user(self, user_data: Dict[str, Any]) -> bool:
        """Add or update user in database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.utcnow().isoformat()
                
                await db.execute('''
                    INSERT INTO users (
                        user_id, username, first_name, last_name, 
                        created_at, updated_at, current_stage, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        updated_at = excluded.updated_at,
                        is_active = 1
                ''', (
                    user_data['user_id'],
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    now,
                    now,
                    'welcome',
                    1
                ))
                
                await db.commit()
            
            logger.info(f"User {user_data['user_id']} added/updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_data.get('user_id')}: {e}", exc_info=True)
            return False
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    'SELECT * FROM users WHERE user_id = ?', (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
            return None
    
    async def update_user_stage(self, user_id: int, stage: str) -> bool:
        """Update user's current funnel stage"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE users 
                    SET current_stage = ?, updated_at = ?
                    WHERE user_id = ?
                ''', (stage, datetime.utcnow().isoformat(), user_id))
                await db.commit()
            
            logger.info(f"User {user_id} stage updated to {stage}")
            return True
        except Exception as e:
            logger.error(f"Error updating user {user_id} stage: {e}", exc_info=True)
            return False
    
    async def add_event(self, user_id: int, event_type: str, event_data: str = None) -> bool:
        """Log user event"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO user_events (user_id, event_type, event_data, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, event_type, event_data, datetime.utcnow().isoformat()))
                await db.commit()
            
            logger.info(f"Event logged: {event_type} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error logging event for user {user_id}: {e}", exc_info=True)
            return False
    
    async def schedule_message(self, user_id: int, stage: str, scheduled_at: datetime) -> bool:
        """Schedule a message for user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO scheduled_messages (user_id, stage, scheduled_at)
                    VALUES (?, ?, ?)
                ''', (user_id, stage, scheduled_at.isoformat()))
                await db.commit()
            
            logger.info(f"Message scheduled for user {user_id} at {scheduled_at}")
            return True
        except Exception as e:
            logger.error(f"Error scheduling message for user {user_id}: {e}", exc_info=True)
            return False
    
    async def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Get all pending scheduled messages"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                now = datetime.utcnow().isoformat()
                
                async with db.execute('''
                    SELECT * FROM scheduled_messages 
                    WHERE sent = 0 AND scheduled_at <= ?
                    ORDER BY scheduled_at ASC
                ''', (now,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending messages: {e}", exc_info=True)
            return []
    
    async def mark_message_sent(self, message_id: int) -> bool:
        """Mark scheduled message as sent"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scheduled_messages 
                    SET sent = 1, sent_at = ?
                    WHERE id = ?
                ''', (datetime.utcnow().isoformat(), message_id))
                await db.commit()
            
            logger.info(f"Message {message_id} marked as sent")
            return True
        except Exception as e:
            logger.error(f"Error marking message {message_id} as sent: {e}", exc_info=True)
            return False
    
    async def increment_retry_count(self, message_id: int) -> bool:
        """Increment retry count for failed message"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scheduled_messages 
                    SET retry_count = retry_count + 1
                    WHERE id = ?
                ''', (message_id,))
                await db.commit()
            
            logger.info(f"Retry count incremented for message {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error incrementing retry count for message {message_id}: {e}", exc_info=True)
            return False
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM users ORDER BY created_at DESC') as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all users: {e}", exc_info=True)
            return []
    
    async def get_stats(self) -> Dict[str, int]:
        """Get bot statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                    total = (await cursor.fetchone())[0]
                
                async with db.execute('SELECT COUNT(*) FROM users WHERE is_active = 1') as cursor:
                    active = (await cursor.fetchone())[0]
                
                async with db.execute('SELECT COUNT(*) FROM scheduled_messages WHERE sent = 1') as cursor:
                    sent = (await cursor.fetchone())[0]
                
                stats = {
                    'total_users': total,
                    'active_users': active,
                    'messages_sent': sent
                }
                
                logger.info(f"Stats retrieved: {stats}")
                return stats
        except Exception as e:
            logger.error(f"Error getting stats: {e}", exc_info=True)
            return {'total_users': 0, 'active_users': 0, 'messages_sent': 0}

db = Database()
