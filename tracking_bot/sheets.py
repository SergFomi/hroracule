import gspread
from config import SPREADSHEET_ID
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from config import SPREADSHEET_NAME, WORKSHEET_NAME, TIMEZONE

class SheetsLogger:
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
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

