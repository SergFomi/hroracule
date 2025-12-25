import os

# Telegram
BOT_TOKEN = "твой_токен_бота"
ADMIN_ID = твой_telegram_id  # чтобы бот слал только тебе

# Google Sheets
SPREADSHEET_NAME = "название_твоей_таблицы"  # или ID таблицы
WORKSHEET_NAME = "Лист1"  # или как у тебя называется

# Timezone
TIMEZONE = "Asia/Ho_Chi_Minh"  # UTC+7 для Вьетнама

# Расписание вопросов
SCHEDULE = [
    {"time": "09:30", "question": "Какой уровень энергии?", "type": "scale", "range": (1, 10)},
    {"time": "09:30", "question": "Зубы утром?", "type": "yes_no"},
    {"time": "09:30", "question": "План на день?", "type": "text"},
    {"time": "09:30", "question": "Во сколько вчера лег?", "type": "choice", "options": ["22-00", "после 00"]},
    {"time": "12:00", "question": "Завтрак?", "type": "yes_no"},
    {"time": "15:00", "question": "Обед?", "type": "yes_no"},
    {"time": "18:00", "question": "Ужин?", "type": "yes_no"},
    {"time": "19:00", "question": "Спорт?", "type": "yes_no"},
    {"time": "21:00", "question": "Что делал сегодня?", "type": "text"},
    {"time": "21:00", "question": "Продуктивность?", "type": "scale", "range": (1, 10)},
    {"time": "21:00", "question": "Какие проблемы беспокоят?", "type": "text"},
]
