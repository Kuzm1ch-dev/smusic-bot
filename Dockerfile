# Используем базовый образ Python
FROM python:3.11-slim-buster

# Устанавливаем системные зависимости для FFmpeg и PyNaCl
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsodium-dev \
    libopus0 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
# Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем папку для загрузок
RUN mkdir -p downloads

# ENV COOKIES_FILE=cookies.txt  # Если используете куки

# Запуск бота
CMD ["python", "main.py"]