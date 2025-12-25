from asyncio import Queue

# Добавь после инициализации
question_queue = Queue()
currently_asking = False

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
