# Базовый образ Python 3.10 (оптимальный для Tinkoff API)
FROM python:3.10-slim as builder

# Установка системных зависимостей (если нужны)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем только requirements.txt для кэширования слоя
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --user --no-cache-dir -r requirements.txt

# Второй этап - минимальный образ
FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости из builder
COPY --from=builder /root/.local /root/.local

# Копируем исходный код (исключая ненужное через .dockerignore)
COPY . .

# Добавляем .local/bin в PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONPATH=/app

# Точка входа
CMD ["python", "-m", "src.main"]


