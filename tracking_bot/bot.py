import asyncio
import logging
import json
import os
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from aiohttp import web

# Добавляем текущую директорию в путь Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import BOT_TOKEN, ADMIN_ID, SCHEDULE, TIMEZONE
    from sheets import SheetsLogger
    logging.info("✅ Все модули импортированы успешно")
except ImportError as e:
    logging.error(f"❌ Ошибка импорта: {e}")
    logging.error(f"Текущая директория: {os.getcwd()}")
    logging.error(f"Содержимое директории: {os.listdir('.')}")
    raise

# Инициализация
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
sheets = SheetsLogger()
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))

# Хранилище ожидаемых ответов и очередь вопросов
pending_questions = {}
question_queue = asyncio.Queue()
currently_asking = False

# Определяем путь для файла состояния с приоритетом /data
# Это важно для работы с персистентным хранилищем в Docker
if os.path.exists('/data'):
    STATE_FILE = "/data/bot_state.json"
    logging.info("📁 Используем /data для сохранения состояния")
else:
    STATE_FILE = "bot_state.json"
    logging.info("📁 Используем текущую директорию для сохранения состояния")

# === Сохранение и загрузка состояния ===

def save_state():
    """Сохраняет состояние бота в файл"""
    try:
        # Собираем состояние
        state = {
            "pending_questions": pending_questions,
            "currently_asking": currently_asking,
            "question_queue": list(question_queue._queue)
        }
        
        # Создаем директорию для файла состояния, если её нет
        state_dir = os.path.dirname(STATE_FILE)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)
            logging.info(f"📁 Создана директория для состояния: {state_dir}")
        
        # Сохраняем в файл
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        logging.info(f"💾 Состояние сохранено в {STATE_FILE}")
        logging.info(f"  - В очереди: {len(state['question_queue'])} вопросов")
        logging.info(f"  - Ожидает ответа: {'Да' if ADMIN_ID in pending_questions else 'Нет'}")
        
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения состояния: {e}")
        logging.error(f"Путь к файлу: {STATE_FILE}")
        logging.error(f"Директория существует: {os.path.exists(os.path.dirname(STATE_FILE))}")

def load_state():
    """Загружает состояние бота из файла"""
    global pending_questions, currently_asking
    
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
                # Восстанавливаем основные переменные
                pending_questions = state.get("pending_questions", {})
                currently_asking = state.get("currently_asking", False)
                
                # Очищаем текущую очередь
                while not question_queue.empty():
                    question_queue.get_nowait()
                
                # Загружаем сохранённые вопросы
                saved_queue = state.get("question_queue", [])
                loaded_count = 0
                for q in saved_queue:
                    try:
                        question_queue.put_nowait(q)
                        loaded_count += 1
                    except Exception as e:
                        logging.error(f"❌ Ошибка загрузки вопроса из состояния: {e}")
                
                logging.info(f"📂 Состояние загружено из {STATE_FILE}")
                logging.info(f"  - Загружено в очередь: {loaded_count}/{len(saved_queue)} вопросов")
                logging.info(f"  - Ожидает ответа: {'Да' if ADMIN_ID in pending_questions else 'Нет'}")
                
                # Если есть ожидающий вопрос, но бот не спрашивает, исправляем состояние
                if ADMIN_ID in pending_questions and not currently_asking:
                    currently_asking = True
                    logging.info("🔄 Восстанавливаем флаг currently_asking")
                    
        else:
            logging.info("📭 Файл состояния не найден, начинаем с чистого состояния")
            
    except json.JSONDecodeError as e:
        logging.error(f"❌ Ошибка чтения JSON из файла состояния: {e}")
        logging.info("🔄 Начинаем с чистого состояния")
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки состояния: {e}")
        logging.info("🔄 Начинаем с чистого состояния")

# === Web Server для keep-alive ===

async def health_check(request):
    return web.Response(text="Bot is running ✅")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
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
    save_state()

async def process_queue():
    """Обрабатывает очередь вопросов"""
    global currently_asking
    
    if currently_asking or question_queue.empty():
        return
    
    currently_asking = True
    question_data = await question_queue.get()
    
    # Сохраняем весь объект вопроса
    pending_questions[ADMIN_ID] = question_data
    
    question = question_data["question"]
    q_type = question_data["type"]
    
    try:
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
        
        logging.info(f"📨 Отправлен вопрос: {question[:50]}...")
        save_state()
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки вопроса: {e}")
        # Если не удалось отправить, освобождаем флаг и возвращаем вопрос в очередь
        currently_asking = False
        # Возвращаем вопрос в начало очереди
        await question_queue.put(question_data)
        save_state()
        # Пробуем обработать следующий вопрос
        await process_queue()

async def finish_current_question():
    """Завершает текущий вопрос и запускает следующий"""
    global currently_asking
    currently_asking = False
    save_state()
    await process_queue()

# === Обработчики ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 Бот для трекинга запущен!\n\nВопросы будут приходить по расписанию.")

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    """Показывает текущее состояние бота"""
    if message.from_user.id != ADMIN_ID:
        return
    
    status = f"""🔍 Статус бота:
📋 В очереди: {question_queue.qsize()} вопросов
⏳ Ждёт ответа: {'Да' if ADMIN_ID in pending_questions else 'Нет'}
🔒 currently_asking: {currently_asking}
📁 Файл состояния: {STATE_FILE}
✅ Файл существует: {os.path.exists(STATE_FILE)}
"""
    
    # Показываем текущий ожидающий вопрос, если есть
    if ADMIN_ID in pending_questions:
        current_q = pending_questions[ADMIN_ID].get("question", "")
        status += f"\n❓ Текущий вопрос: {current_q[:50]}..."
    
    await message.answer(status)

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сбрасывает состояние бота"""
    if message.from_user.id != ADMIN_ID:
        return
    
    global currently_asking
    pending_questions.clear()
    currently_asking = False
    
    # Очищаем очередь
    while not question_queue.empty():
        try:
            question_queue.get_nowait()
        except:
            break
    
    save_state()
    await message.answer("✅ Состояние сброшено. Новые вопросы придут по расписанию.")
    logging.info("🔄 Состояние бота сброшено через команду /reset")

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
        
        logging.info(f"✅ Ответ записан: {question[:30]}... → {answer}")
        
        await finish_current_question()
        save_state()

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
        
        logging.info(f"✅ Текстовый ответ записан: {question[:30]}... → {answer[:30]}...")
        
        await finish_current_question()
        save_state()
    else:
        # Это дневниковая запись
        sheets.log_answer("Дневниковая запись", message.text)
        await message.answer("📝 Записал в дневник")
        logging.info(f"📝 Дневниковая запись: {message.text[:50]}...")

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
            logging.info(f"⏰ Сработало расписание на {time}, отправляю {len(q_list)} вопросов")
            for q in q_list:
                await question_queue.put(q)
            await process_queue()
            save_state()
        
        scheduler.add_job(
            send_batch,
            CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            id=f"batch_{time}"
        )
        
        logging.info(f"📅 Запланировано {len(questions)} вопросов на {time}")

# === Запуск ===

async def main():
    logging.info("=" * 50)
    logging.info("🚀 Запуск бота...")
    logging.info(f"Текущая директория: {os.getcwd()}")
    logging.info(f"Файлы в директории: {os.listdir('.')}")
    
    # Проверяем доступность /data
    if os.path.exists('/data'):
        logging.info("✅ Директория /data доступна")
        try:
            logging.info(f"Содержимое /data: {os.listdir('/data')}")
        except Exception as e:
            logging.warning(f"⚠️ Не удалось прочитать содержимое /data: {e}")
    else:
        logging.info("⚠️ Директория /data недоступна, состояние будет сохранено локально")
    
    load_state()
    
    asyncio.create_task(start_web_server())
    setup_schedule()
    scheduler.start()
    
    logging.info("✅ Бот успешно запущен!")
    logging.info("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Ошибка в работе бота: {e}")
        save_state()  # Пытаемся сохранить состояние перед падением
        raise
    finally:
        logging.info("💾 Сохраняю состояние перед завершением...")
        save_state()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Бот остановлен пользователем")
        save_state()
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        save_state()
        raise
