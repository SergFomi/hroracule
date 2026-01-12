import gspread
import logging
import json
from datetime import datetime
from typing import Dict, Any, List
from oauth2client.service_account import ServiceAccountCredentials
from config import config

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.sheet = None
        self.worksheet = None
        self._init_sheets()
    
    def _init_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            logger.info("Initializing Google Sheets connection...")
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                config.GOOGLE_CREDENTIALS, 
                scope
            )
            
            client = gspread.authorize(credentials)
            self.sheet = client.open_by_key(config.GOOGLE_SHEET_ID)
            
            # Get or create first worksheet
            try:
                self.worksheet = self.sheet.get_worksheet(0)
            except Exception:
                self.worksheet = self.sheet.add_worksheet(title="Users", rows=1000, cols=20)
            
            # Initialize headers if needed
            self._init_headers()
            
            logger.info("Google Sheets initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}", exc_info=True)
            raise
    
    def _init_headers(self):
        """Initialize spreadsheet headers"""
        try:
            headers = self.worksheet.row_values(1)
            
            if not headers or headers[0] != 'Timestamp':
                expected_headers = [
                    'Timestamp',
                    'User ID',
                    'Username',
                    'First Name',
                    'Last Name',
                    'Phone',
                    'Link',
                    'UTM Source',
                    'UTM Medium',
                    'UTM Campaign',
                    'Current Stage',
                    'Is Active',
                    'Last Activity'
                ]
                
                self.worksheet.update('A1:M1', [expected_headers])
                logger.info("Headers initialized in Google Sheets")
        except Exception as e:
            logger.error(f"Error initializing headers: {e}", exc_info=True)
    
    def _create_user_link(self, user_id: int, username: str = None) -> str:
        """Create Telegram user link"""
        if username:
            return f"https://t.me/{username}"
        return f"tg://user?id={user_id}"
    
    async def add_user(self, user_data: Dict[str, Any]) -> bool:
        """Add or update user in Google Sheets"""
        try:
            user_id = user_data['user_id']
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # Check if user exists
            cell = self.worksheet.find(str(user_id), in_column=2)
            
            row_data = [
                timestamp,
                user_id,
                user_data.get('username', ''),
                user_data.get('first_name', ''),
                user_data.get('last_name', ''),
                user_data.get('phone', ''),
                self._create_user_link(user_id, user_data.get('username')),
                user_data.get('utm_source', ''),
                user_data.get('utm_medium', ''),
                user_data.get('utm_campaign', ''),
                user_data.get('current_stage', 'welcome'),
                'Yes' if user_data.get('is_active', True) else 'No',
                timestamp
            ]
            
            if cell:
                # Update existing row
                row_num = cell.row
                self.worksheet.update(f'A{row_num}:M{row_num}', [row_data])
                logger.info(f"Updated user {user_id} in Google Sheets (row {row_num})")
            else:
                # Append new row
                self.worksheet.append_row(row_data)
                logger.info(f"Added new user {user_id} to Google Sheets")
            
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_data.get('user_id')} to Sheets: {e}", exc_info=True)
            return False
    
    async def update_user_stage(self, user_id: int, stage: str) -> bool:
        """Update user's current stage in Google Sheets"""
        try:
            cell = self.worksheet.find(str(user_id), in_column=2)
            
            if cell:
                row_num = cell.row
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                
                # Update stage and last activity
                self.worksheet.update(f'K{row_num}', [[stage]])  # Current Stage
                self.worksheet.update(f'M{row_num}', [[timestamp]])  # Last Activity
                
                logger.info(f"Updated stage for user {user_id} to {stage} in Sheets")
                return True
            else:
                logger.warning(f"User {user_id} not found in Sheets")
                return False
        except Exception as e:
            logger.error(f"Error updating user {user_id} stage in Sheets: {e}", exc_info=True)
            return False
    
    async def sync_user(self, user_data: Dict[str, Any]) -> bool:
        """Sync user data to Google Sheets"""
        return await self.add_user(user_data)
    
    async def batch_sync_users(self, users: List[Dict[str, Any]]) -> int:
        """Batch sync multiple users to Google Sheets"""
        success_count = 0
        
        for user in users:
            if await self.add_user(user):
                success_count += 1
        
        logger.info(f"Batch synced {success_count}/{len(users)} users to Google Sheets")
        return success_count

sheets_service = GoogleSheetsService()
