# Инструкция по деплою на Render

## 1. Подготовка Google Sheets

1. Создай Google Sheet
2. Перейди в [Google Cloud Console](https://console.cloud.google.com/)
3. Создай новый проект или выбери существующий
4. Включи Google Sheets API и Google Drive API
5. Создай Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - Скачай JSON ключ
6. Скопируй email Service Account (вида `...@....iam.gserviceaccount.com`)
7. Расшарь свою Google таблицу на этот email (права: Editor)
8. Скопируй ID таблицы из URL: `https://docs.google.com/spreadsheets/d/{ID}/edit`

## 2. Создание Telegram бота

1. Найди [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям
4. Сохрани токен бота
5. Узнай свой Telegram ID через [@userinfobot](https://t.me/userinfobot)

## 3. Подготовка канала (опционально)

1. Создай публичный канал
2. Добавь бота в канал как администратора
3. Опубликуй пост с гайдом
4. Узнай ID поста (правый клик → Copy Link)
5. Запиши username канала (формат: `@channel_name`) или ID

## 4. Деплой на Render

### Вариант А: Через Dashboard

1. Зайди на [Render.com](https://render.com/)
2. New → Web Service
3. Connect твой GitHub репозиторий
4. Настройки:
   - Name: `kk-funnel-bot`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
5. Добавь Environment Variables (см. ниже)
6. Deploy!

### Вариант Б: Через render.yaml

1. Пуш код в GitHub
2. На Render: New → Blueprint
3. Connect репозиторий
4. Render автоматически найдет `render.yaml`
5. Добавь Environment Variables вручную (они не могут быть в YAML по безопасности)
6. Deploy!

## 5. Environment Variables на Render

Добавь следующие переменные:

```
KK_TELEGRAM_BOT_TOKEN = 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
KK_TELEGRAM_CHANNEL_ID = @your_channel
KK_GOOGLE_SHEETS_CREDENTIALS = {"type":"service_account",...весь JSON...}
KK_GOOGLE_SHEET_ID = 1a2b3c4d5e6f7g8h9i0j
KK_ADMIN_USER_IDS = 123456789,987654321
KK_UPTIME_ROBOT_MONITOR = true
```

**Важно для `KK_GOOGLE_SHEETS_CREDENTIALS`:**
- Весь JSON из скачанного файла credentials.json
- Должен быть в одну строку (минимизирован)
- Если есть переносы строк - убери их

## 6. Настройка UptimeRobot

1. Зайди на [UptimeRobot.com](https://uptimerobot.com/)
2. Add New Monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: `KK Funnel Bot`
   - URL: `https://your-app-name.onrender.com/health`
   - Monitoring Interval: 5 minutes
3. Save!

## 7. Настройка конфигурации воронки

### Обновление ID поста в канале

Отредактируй `config/messages.yml`:

```yaml
guide_intro:
  text: "Вот подробный гайд по поиску удаленной работы:"
  forward_from_channel: true
  channel_post_id: 123  # <-- ЗАМЕНИ на реальный ID поста
```

Как узнать ID поста:
1. Открой пост в канале
2. Правый клик → Copy Link
3. Ссылка будет вида: `https://t.me/channel_name/123`
4. Число в конце (123) - это ID поста

### Добавление медиа файлов

1. Положи файлы в папку `media/`
2. Укажи путь в `config/messages.yml`:

```yaml
resume_sample:
  text: "Вот образец резюме:"
  file_path: "media/resume_sample.pdf"  # путь относительно папки media/
```

## 8. Проверка работы

1. Найди своего бота в Telegram
2. Отправь `/start`
3. Должно прийти приветственное сообщение
4. Проверь Google Sheets - должна появиться новая строка с твоими данными
5. Проверь логи на Render (Dashboard → Logs)

## 9. Получение deep link для лендинга

Deep link с UTM параметрами:

```
https://t.me/your_bot_username?start=source-medium-campaign
```

Примеры:
- `https://t.me/your_bot?start=instagram-stories-jan2024`
- `https://t.me/your_bot?start=facebook-ads-test`

Параметры автоматически сохранятся в Google Sheets.

## 10. Админские команды

В Telegram отправь боту:
- `/stats` - статистика
- `/reload` - перезагрузить конфиг воронки
- `/broadcast` - рассылка (ответь на сообщение)
- `/help` - помощь

## Troubleshooting

### Бот не отвечает
1. Проверь логи на Render
2. Проверь Environment Variables
3. Проверь что UptimeRobot пингует `/health`

### Ошибка Google Sheets
1. Проверь что таблица расшарена на Service Account email
2. Проверь что JSON credentials валиден (одна строка, нет лишних пробелов)
3. Проверь что включены Google Sheets API и Drive API

### Файлы не отправляются
1. Проверь что файлы загружены в `media/`
2. Проверь пути в `config/messages.yml`
3. На Render Free plan может быть лимит на размер файлов

### Не пересылаются посты из канала
1. Проверь что бот добавлен в канал как администратор
2. Проверь что ID поста правильный
3. Проверь что `KK_TELEGRAM_CHANNEL_ID` указан верно (формат: `@channel_name` или числовой ID)

## Полезные ссылки

- [Render Docs](https://render.com/docs)
- [Aiogram Docs](https://docs.aiogram.dev/)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Telegram Bot API](https://core.telegram.org/bots/api)
