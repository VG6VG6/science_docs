FROM python:3.12-slim

WORKDIR /app

# Настройка переменных окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода проекта
COPY . .

# Создание директории bin для баз данных и конфигураций если её нет
RUN mkdir -p /app/bin /app/bin/requests

# Права на выполнение для скрипта запуска
RUN chmod +x /app/main.py

# Открываем порт для FastAPI
EXPOSE 8000

# Команда для запуска Uvicorn
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
