import asyncio
import logging
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, SCHEDULE, TIMEZONE
from sheets import SheetsLogger

# Инициализация
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
sheets = SheetsLogger()
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))

# Хранилище ожидаемых ответов и очередь вопросов
pending_questions = {}
question_queue = asyncio.Queue()
currently_asking = False

# Файл для сохранения состояния
STATE_FILE = "bot_state.json"

# === Сохранение и загрузка состояния ===

def save_state():
    """Сохраняет состояние бота в файл"""
    state = {
        "pending_questions": pending_questions,
        "currently_asking": currently_asking,
        "question_queue": list(question_queue._queue)  # Преобразуем очередь в список
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    logging.info("💾 Состояние сохранено")

def load_state():
    """Загружает состояние бота из файла"""
    global pending_questions, currently_asking
    
    if not os.path.exists(STATE_FILE):
        logging.info("📭 Файл состояния не найден, начинаем с чистого состояния")
        return
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            pending_questions = state.get("pending_questions", {})
            currently_asking = state.get("currently_asking", False)
            
            # Очищаем очередь и загружаем сохранённые вопросы
            while not question_queue.empty():
                question_queue.get_nowait()
            
            for q in state.get("question_queue", []):
                question_queue.put_nowait(q)
            
            logging.info(f"📂 Состояние загружено: {len(state.get('question_queue', []))} вопросов в очереди")
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки состояния: {e}")

# === Web Server для keep-alive ===

async def health_check(request):
    return web.Response(text="Bot is running ✅")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Изменено на порт 8080 для Coolify
    await site.start()
    logging.info("🌐 Web server started on port 8080")

# === Создание клавиатур ===

def create_yes_no_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="answer:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="answer:no")
        ]
    ])

def create_scale_keyboard(min_val: int, max_val: int):
    buttons = []
    row = []
    for i in range(min_val, max_val + 1):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"answer:{i}"))
        if len(row) == 5:  # 5 кнопок в ряд
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_choice_keyboard(options: list):
    buttons = [[InlineKeyboardButton(text=opt, callback_data=f"answer:{opt}")] for opt in options]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# === Отправка вопросов с очередью ===

async def send_question(question_data: dict):
    """Добавляет вопрос в очередь"""
    await question_queue.put(question_data)
    await process_queue()
    save_state()  # Сохраняем состояние после добавления вопроса

async def process_queue():
    """Обрабатывает очередь вопросов"""
    global currently_asking
    
    if currently_asking or question_queue.empty():
        return
    
    currently_asking = True
    question_data = await question_queue.get()
    
    # Сохраняем весь объект вопроса, а не только текст
    pending_questions[ADMIN_ID] = question_data
    
    question = question_data["question"]
    q_type = question_data["type"]
    
    if q_type == "yes_no":
        await bot.send_message(ADMIN_ID, question, reply_markup=create_yes_no_keyboard())
    
    elif q_type == "scale":
        min_val, max_val = question_data["range"]
        await bot.send_message(ADMIN_ID, question, reply_markup=create_scale_keyboard(min_val, max_val))
    
    elif q_type == "choice":
        options = question_data["options"]
        await bot.send_message(ADMIN_ID, question, reply_markup=create_choice_keyboard(options))
    
    elif q_type == "text":
        await bot.send_message(ADMIN_ID, f"📝 {question}\n\n_(просто напиши ответ текстом)_", parse_mode="Markdown")
    
    save_state()  # Сохраняем состояние после отправки вопроса

async def finish_current_question():
    """Завершает текущий вопрос и запускает следующий"""
    global currently_asking
    currently_asking = False
    await process_queue()
    save_state()  # Сохраняем состояние после завершения вопроса

# === Обработчики ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 Бот для трекинга запущен!\n\nВопросы будут приходить по расписанию.")

@dp.callback_query(F.data.startswith("answer:"))
async def handle_button_answer(callback: types.CallbackQuery):
    """Обработка ответов через кнопки"""
    if callback.from_user.id != ADMIN_ID:
        return
    
    answer = callback.data.split(":", 1)[1]
    
    # Переводим yes/no в читаемый вид
    if answer == "yes":
        answer = "Да"
    elif answer == "no":
        answer = "Нет"
    
    question_data = pending_questions.get(ADMIN_ID)
    if question_data:
        question = question_data["question"]
        
        # Записываем в таблицу
        sheets.log_answer(question, answer)
        
        # Удаляем вопрос из ожидаемых
        pending_questions.pop(ADMIN_ID, None)
        
        await callback.message.edit_text(f"✅ {question}\n\n→ {answer}")
        await callback.answer()
        
        await finish_current_question()
        save_state()  # Сохраняем состояние после ответа

@dp.message(F.text)
async def handle_text_answer(message: types.Message):
    """Обработка текстовых ответов и дневниковых записей"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID in pending_questions:
        # Это ответ на вопрос
        question_data = pending_questions[ADMIN_ID]
        question = question_data["question"]
        answer = message.text
        
        sheets.log_answer(question, answer)
        pending_questions.pop(ADMIN_ID, None)
        
        await message.answer(f"✅ Записано:\n\n_{question}_\n→ {answer}", parse_mode="Markdown")
        
        await finish_current_question()
        save_state()  # Сохраняем состояние после ответа
    else:
        # Это дневниковая запись
        sheets.log_answer("Дневниковая запись", message.text)
        await message.answer("📝 Записал в дневник")

# === Настройка расписания ===

def setup_schedule():
    """Настраивает все вопросы по расписанию"""
    # Группируем вопросы по времени
    questions_by_time = {}
    for item in SCHEDULE:
        time = item["time"]
        if time not in questions_by_time:
            questions_by_time[time] = []
        questions_by_time[time].append(item)
    
    # Создаём задачи для каждого времени
    for time, questions in questions_by_time.items():
        hour, minute = map(int, time.split(":"))
        
        async def send_batch(q_list=questions):
            """Отправляет пачку вопросов в очередь"""
            for q in q_list:
                await question_queue.put(q)
            await process_queue()
            save_state()  # Сохраняем состояние после добавления вопросов
        
        scheduler.add_job(
            send_batch,
            CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            id=f"batch_{time}"
        )
        
        logging.info(f"📅 Запланировано {len(questions)} вопросов на {time}")

# === Запуск ===

async def main():
    load_state()  # Загружаем сохранённое состояние
    asyncio.create_task(start_web_server())
    setup_schedule()
    scheduler.start()
    logging.info("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
