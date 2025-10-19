# French Quiz Telegram Bot

Простая структура проекта для викторины по французскому языку.

Структура:

├── bot/
│   ├── main.py              # aiogram логика
│   ├── handlers/
│   │   ├── start.py
│   │   └── quiz.py
│   └── states.py
├── backend/
│   ├── app.py               # FastAPI
│   └── data/questions.json
├── data/
│   └── audio/*.mp3
├── requirements.txt
└── README.md

Poetry (рекомендованный способ — для изоляции зависимостей и удобного деплоя)

1. Установите Poetry (если ещё не установлен):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Установите зависимости и создайте виртуальное окружение:

```bash
poetry install
```

3. Запуск бэкенда через Poetry:

```bash
poetry run start-backend
# по умолчанию запустится на 127.0.0.1:8000
```

4. Запуск бота через Poetry:

```bash
# Установите токен в переменной окружения API_TOKEN
poetry run start-bot
```

Альтернативы без Poetry (быстрое локальное тестирование):

```bash
python -m pip install -r requirements.txt
uvicorn backend.app:app --reload
python -m bot.main
```

Примечание: добавьте аудиофайлы в `data/audio/` и при необходимости обновите `backend/data/questions.json`.

Лицензия: MIT


Заметки по расширению

Порядок и рандом: перед стартом перемешай question_ids.

Хранилище: SESSIONS/QUESTIONS → Redis/Postgres (миграция без изменения контрактов).

Защита: можно добавить X-Api-Key для вызовов только от бота.

Повторы (SRS): на будущее — отдельные эндпоинты, здесь квиз «линейный» по N вопросам.