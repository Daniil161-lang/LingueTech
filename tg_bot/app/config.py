from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Обязательные переменные. Добавь их в Environment Variables в Render
    bot_token: str
    channel_username: str
    database_url: str  # Render предоставит строку подключения к своему PostgreSQL
    webhook_secret: str  # Секретный ключ для webhook URL
    
    # Опциональные переменные с значениями по умолчанию
    webhook_base_url: str = "https://your-service-name.onrender.com"  # Будет меняться
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()