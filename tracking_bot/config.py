import os

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")  # ID таблицы
WORKSHEET_NAME = "track"

# Timezone
TIMEZONE = "Asia/Ho_Chi_Minh"

# Расписание вопросов
SCHEDULE = [
    {"time": "08:30", "question": "Какой уровень энергии?", "type": "scale", "range": (1, 10)},
    {"time": "10:30", "question": "Встал в 8:00?", "type": "yes_no"},
    {"time": "10:30", "question": "Зубы утром?", "type": "yes_no"},
    {"time": "08:30", "question": "План на день?", "type": "text"},
    {"time": "08:30", "question": "Во сколько вчера лег?", "type": "choice", "options": ["23-00", "после 00"]},
    {"time": "08:30", "question": "Одна важная вещь сегодня?", "type": "text"},
    {"time": "11:00", "question": "Завтрак?", "type": "yes_no"},
    {"time": "15:00", "question": "Обед?", "type": "yes_no"},
    {"time": "19:00", "question": "Ужин?", "type": "yes_no"},
    {"time": "19:00", "question": "Было медленное медитативное удовольствие сегодня? Если нет, делай щас", "type": "choice", "options": ["Да, было", "Нет, делаю"]},
    {"time": "19:00", "question": "Встречал человека с классификацией DISC?", "type": "text"},
    {"time": "19:00", "question": "Спорт?", "type": "yes_no"},
    {"time": "21:00", "question": "Что делал сегодня?", "type": "text"},
    {"time": "21:00", "question": "Сделал важную вещь?", "type": "yes_no"},
    {"time": "21:00", "question": "Продуктивность?", "type": "scale", "range": (1, 10)},
    {"time": "21:00", "question": "Какие проблемы беспокоят?", "type": "text"},
    {"time": "21:00", "question": "Фокусы на неделю?", "type": "text"},
    {"time": "21:00", "question": "Сколько калорий сегодня?", "type": "text"},
]
