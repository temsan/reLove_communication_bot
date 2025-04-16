# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем переменную окружения для Poetry
ENV POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

# Устанавливаем Poetry
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY pyproject.toml poetry.lock* ./

# Устанавливаем зависимости, не включая dev
# --no-root нужен, чтобы не устанавливать сам пакет relove_bot на этом этапе
RUN poetry install --no-interaction --no-ansi --no-dev --no-root

# Копируем код приложения
# Добавляем точку в конце для копирования всего содержимого текущей директории
# (предполагая, что Dockerfile в корне)
COPY . .

# Устанавливаем пакет relove_bot (теперь можно, т.к. код скопирован)
RUN poetry install --no-interaction --no-ansi --no-dev

# Указываем команду для запуска приложения
CMD ["python", "-m", "relove_bot.main"] 