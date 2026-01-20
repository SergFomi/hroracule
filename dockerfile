dockerfile
FROM python:3.11-slim

# Рабочая директория в контейнере
WORKDIR /app

# Копируем папку tracking_bot в /app
COPY tracking_bot/ /app/

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для данных
RUN mkdir -p /data

# Открываем порт для health check
EXPOSE 8080

# Запускаем бота
CMD ["python", "bot.py"]
