from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Директория для аудио файлов
    AUDIO_OUTPUT_DIR: Path = Path('backend/data/audio')
    
    # Настройки для TTS (могут быть расширены позже)
    TTS_LANG: str = "fr"
    # Выбор поставщика TTS (например: 'google', 'gtts', 'azure')
    TTS_PROVIDER: str | None = None
    # Уровень логирования
    LOG_LEVEL: str = "INFO"
    
    # Настройки для бота / клиента
    # Токен Telegram-бота (пустая строка по умолчанию — безопасно)
    BOT_TOKEN: str = ""
    # Базовый URL API (FastAPI)
    API_BASE: str = "http://127.0.0.1:8000"
    # Количество вопросов по умолчанию
    N_QUESTIONS: int = 3
    # Опциональный токен для авторизации запросов к backend (Bearer)
    API_TOKEN: str = ""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True
    )


# Создаем глобальный экземпляр настроек
settings = Settings()