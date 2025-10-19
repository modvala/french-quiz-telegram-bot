# Backend service Dockerfile
FROM python:3.11-slim

# set workdir
WORKDIR /app

# avoid Python buffering
ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_HOME="/opt/poetry" \
    PATH="$POETRY_HOME/bin:$PATH"

# install system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# install poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - --version 1.8.2 \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && poetry --version

# copy only pyproject and poetry.lock first for dependency install
COPY pyproject.toml poetry.lock* /app/

# install dependencies
RUN poetry install --no-interaction --no-ansi --only main --no-root

# copy project files
COPY . /app

# expose port and default command
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
