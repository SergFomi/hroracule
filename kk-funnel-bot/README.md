# KK Funnel Bot

Telegram-бот для автоматической воронки с интеграцией Google Sheets.

## Установка

1. Клонируй репозиторий
2. Настрой переменные окружения (см. `.env.example`)
3. Создай Google Sheet и расшарь на Service Account email
4. Деплой на Render

## Environment Variables (Render)

```bash
KK_TELEGRAM_BOT_TOKEN=your_bot_token
KK_TELEGRAM_CHANNEL_ID=@your_channel
KK_GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}
KK_GOOGLE_SHEET_ID=spreadsheet_id
KK_ADMIN_USER_IDS=123456789,987654321
KK_UPTIME_ROBOT_MONITOR=true
```

## Структура воронки

Редактируй `config/funnel.yml` для настройки последовательности сообщений и таймеров.

## UptimeRobot

Пинговать: `https://your-app.onrender.com/health`
Интервал: 5 минут

## Локальный запуск

```bash
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
python main.py
```
