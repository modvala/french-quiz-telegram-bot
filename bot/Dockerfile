# Bot service Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_HOME="/opt/poetry" \
    PATH="$POETRY_HOME/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - --version 1.8.2 \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && poetry --version

# copy pyproject and optional lock
COPY pyproject.toml poetry.lock* /app/

RUN poetry install --no-interaction --no-ansi --only main --no-root

# copy project
COPY . /app

EXPOSE 8090
CMD ["uvicorn", "bot.server:app", "--host", "0.0.0.0", "--port", "8090"]
