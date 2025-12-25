import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import json
import os
import base64
from config import SPREADSHEET_ID, WORKSHEET_NAME, TIMEZONE

class SheetsLogger:
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Читаем из переменной окружения
        creds_base64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
        
        if creds_base64:
            # Декодируем base64 → JSON (для продакшена)
            creds_json = base64.b64decode(creds_base64).decode('utf-8')
            creds_dict = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Локальная разработка
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    
    def log_answer(self, question: str, answer: str):
        """Записывает ответ в таблицу"""
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        
        row = [
            now.strftime("%Y-%m-%d"),  # Date
            now.strftime("%H:%M:%S"),  # Time
            question,                   # Question
            answer                      # Answer
        ]
        
        self.sheet.append_row(row)
        print(f"✅ Записано: {question} → {answer}")
