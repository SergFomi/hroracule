import asyncio
import logging
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

# === Web Server для keep-alive ===

async def health_check(request):
    return web.Response(text="Bot is running ✅")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)  # Render использует порт 10000
    await site.start()
    logging.info("🌐 Web server started on port 10000")

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

async def process_queue():
    """Обрабатывает очередь вопросов"""
    global currently_asking
    
    if currently_asking or question_queue.empty():
        return
    
    currently_asking = True
    question_data = await question_queue.get()
    
    question = question_data["question"]
    q_type = question_data["type"]
    
    # Сохраняем, что ждём ответа на этот вопрос
    pending_questions[ADMIN_ID] = question
    
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

async def finish_current_question():
    """Завершает текущий вопрос и запускает следующий"""
    global currently_asking
    currently_asking = False
    await process_queue()

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
    
    question = pending_questions.get(ADMIN_ID, "Unknown")
    
    # Записываем в таблицу
    sheets.log_answer(question, answer)
    
    # Удаляем вопрос из ожидаемых
    pending_questions.pop(ADMIN_ID, None)
    
    await callback.message.edit_text(f"✅ {question}\n\n→ {answer}")
    await callback.answer()
    
    await finish_current_question()

@dp.message(F.text)
async def handle_text_answer(message: types.Message):
    """Обработка текстовых ответов"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID in pending_questions:
        question = pending_questions[ADMIN_ID]
        answer = message.text
        
        sheets.log_answer(question, answer)
        pending_questions.pop(ADMIN_ID, None)
        
        await message.answer(f"✅ Записано:\n\n_{question}_\n→ {answer}", parse_mode="Markdown")
        
        await finish_current_question()

# === Настройка расписания ===

def setup_schedule():
    """Настраивает все вопросы по расписанию"""
    for item in SCHEDULE:
        hour, minute = map(int, item["time"].split(":"))
        
        scheduler.add_job(
            send_question,
            CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            args=[item],
            id=f"{item['time']}_{item['question']}"
        )
        
        logging.info(f"📅 Запланирован вопрос: {item['time']} → {item['question']}")

# === Запуск ===

async def main():
    asyncio.create_task(start_web_server())
    setup_schedule()
    scheduler.start()
    logging.info("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
