from pathlib import Path
import os

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
    # Базовый URL API (FastAPI)
    API_BASE: str = os.environ.get("API_BASE", "http://127.0.0.1:8080")
    API_TOKEN: str | None = os.environ.get("API_TOKEN", "")
    # Количество вопросов по умолчанию
    N_QUESTIONS: int = 10
    # Токен Telegram-бота (устанавливается через .env как BOT_TOKEN)
    BOT_TOKEN: str | None = ""
    # URL вебхука для Telegram (если используется). Пример: https://domain.tld/tg/webhook
    WEBHOOK_URL: str | None = os.environ.get("WEBHOOK_URL", "https://christinia-noncontagious-bradyauxetically.ngrok-free.dev/tg/webhook")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True
    )


# Создаем глобальный экземпляр настроек
settings = Settings()