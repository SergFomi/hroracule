# Архитектура KK Funnel Bot

## Обзор

Telegram-бот для автоматической воронки продаж с интеграцией Google Sheets и планировщиком отложенных сообщений.

## Компоненты

### 1. Основные модули

```
main.py                 # Точка входа, запуск бота и веб-сервера
config.py              # Конфигурация и валидация переменных окружения
database.py            # SQLite база данных
sheets_service.py      # Интеграция с Google Sheets
scheduler.py           # Планировщик отложенных сообщений
message_sender.py      # Отправка сообщений разных типов
funnel_loader.py       # Загрузка конфигурации воронки из YAML
```

### 2. Handlers (обработчики)

```
handlers/
├── start.py          # Обработка /start, регистрация пользователей
├── callbacks.py      # Обработка inline кнопок
└── admin.py          # Админские команды
```

### 3. Конфигурация

```
config/
├── messages.yml      # Шаблоны сообщений
└── funnel.yml        # Настройки воронки и таймеров
```

### 4. Медиа

```
media/                # Файлы для отправки пользователям
└── *.pdf, *.jpg, etc
```

## Поток данных

### Регистрация нового пользователя

```
1. User → /start
2. start.py → Извлечь UTM параметры
3. database.py → Сохранить в SQLite
4. sheets_service.py → Синхронизировать в Google Sheets
5. scheduler.py → Запланировать воронку
6. message_sender.py → Отправить первое сообщение
```

### Обработка отложенных сообщений

```
1. scheduler.py → Каждую минуту проверяет pending messages
2. database.py → Получить сообщения где scheduled_at <= NOW
3. message_sender.py → Отправить сообщение
4. database.py → Обновить статус (sent = 1)
5. sheets_service.py → Обновить stage в Google Sheets
```

### Обработка callback кнопок

```
1. User → Нажимает кнопку
2. callbacks.py → Обработка callback_data
3. database.py → Логировать событие
4. message_sender.py → Отправить следующее сообщение
5. sheets_service.py → Обновить данные
```

## База данных

### Таблицы

**users**
- user_id (PK)
- username, first_name, last_name
- phone, language_code
- created_at, updated_at
- utm_source, utm_medium, utm_campaign
- current_stage
- is_active

**user_events**
- id (PK)
- user_id (FK)
- event_type
- event_data
- created_at

**scheduled_messages**
- id (PK)
- user_id (FK)
- stage
- scheduled_at
- sent (0/1)
- sent_at
- retry_count

## Google Sheets структура

### Колонки

1. Timestamp - Время создания/обновления
2. User ID - Telegram ID пользователя
3. Username - @username
4. First Name - Имя
5. Last Name - Фамилия
6. Phone - Телефон (если дал)
7. Link - t.me/username или tg://user?id=
8. UTM Source - Источник трафика
9. UTM Medium - Канал
10. UTM Campaign - Кампания
11. Current Stage - Текущий этап воронки
12. Is Active - Активен ли пользователь
13. Last Activity - Последняя активность

## Планировщик (APScheduler)

### Задачи

**process_pending_messages** (каждую минуту)
- Проверяет scheduled_messages
- Отправляет сообщения где scheduled_at <= NOW
- Обрабатывает retry при ошибках
- Обновляет статусы

**sync_to_sheets** (каждые 5 минут)
- Синхронизирует всех пользователей в Google Sheets
- Обновляет данные batch-запросом

## Воронка

### Конфигурация (funnel.yml)

```yaml
funnel:
  - stage: "welcome"
    delay_seconds: 0
    message_key: "welcome"
  
  - stage: "guide"
    delay_seconds: 2
    message_key: "guide_intro"
```

### Типы сообщений

1. **Текстовое** - простой текст
2. **С кнопками** - текст + inline keyboard
3. **С файлом** - текст + документ/фото
4. **Пересылка из канала** - forward_message

### Этапы воронки (пример)

1. **welcome** (0 сек) - Приветствие
2. **guide** (2 сек) - Пересылка гайда из канала
3. **resume** (5 сек) - Отправка образца резюме
4. **webinar_invite** (24 часа) - Приглашение на вебинар
5. **followup_1** (3 дня) - Follow-up сообщение

## Health Check

### Endpoint: /health

```python
GET https://your-app.onrender.com/health
Response: "OK" (200)
```

Используется для:
- UptimeRobot мониторинга
- Предотвращения засыпания на Render Free plan
- Проверки работоспособности

## Логирование

### Уровни

- **INFO** - Обычные события (старт бота, отправка сообщений)
- **WARNING** - Предупреждения (не найден пользователь, неизвестный callback)
- **ERROR** - Ошибки (failed to send message, database error)
- **CRITICAL** - Критические ошибки (invalid config, startup failures)

### Что логируется

- Все действия пользователей
- Отправка каждого сообщения
- Ошибки при отправке
- Синхронизация с Google Sheets
- Планирование и выполнение задач
- Админские команды

## Retry механизм

### Параметры (funnel.yml)

```yaml
settings:
  max_retries: 3
  retry_delay: 300  # 5 минут
```

### Логика

1. Сообщение не отправилось
2. Увеличить retry_count
3. Если retry_count < max_retries → попробовать снова через 5 минут
4. Если retry_count >= max_retries → пометить как sent, логировать ошибку

## Масштабирование

### Текущие лимиты

- **Render Free**: 750 часов/месяц, засыпает через 15 минут неактивности
- **UptimeRobot Free**: мониторинг каждые 5 минут
- **Google Sheets API**: 500 requests/100 seconds/user
- **SQLite**: достаточно для 10k+ пользователей

### Для роста

1. **Render Paid Plan** - не засыпает, больше ресурсов
2. **PostgreSQL** - вместо SQLite для persistence
3. **Redis** - для кеширования и очередей
4. **Batch operations** - группировать обновления Google Sheets
5. **Webhook mode** - вместо long polling для больших нагрузок

## Безопасность

### Хранение секретов

- Все секреты в Environment Variables на Render
- Никогда не коммитить .env
- Google credentials в JSON (одна строка)

### Валидация

- Проверка admin_user_ids перед выполнением команд
- Валидация конфигурации при старте
- Try-except блоки вокруг всех операций

### Логирование

- Не логировать токены и credentials
- Логировать user_id, но не личные данные
- Stack traces только в файл, не в консоль production

## FAQ

**Q: Как добавить новый этап в воронку?**
A: Отредактируй `config/funnel.yml` и `config/messages.yml`, затем `/reload` в боте

**Q: Как изменить текст сообщения?**
A: Отредактируй `config/messages.yml`, затем `/reload`

**Q: Бот отправил сообщение дважды?**
A: Проверь scheduled_messages в БД, возможно duplicate scheduling

**Q: Google Sheets не обновляется?**
A: Проверь логи scheduler.py, возможно rate limit или неверные credentials

**Q: Как добавить новую кнопку?**
A: Добавь в `config/messages.yml` → buttons, затем обработчик в `handlers/callbacks.py`
