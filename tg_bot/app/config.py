from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Обязательные переменные. Добавь их в Environment Variables в Render
    bot_token: str = os.getenv("8226557308:AAFsfj_ZXfX5EVacRezKt5OZhWSC4HbzxwU")
    channel_username: str = os.getenv( "@НАЧАЛО")
    database_url: str  =os.getenv( "postgresql://user:password@localhost/dbname" )# Render предоставит строку подключения к своему PostgreSQL
    webhook_secret: str = os.getenv("17c3940657bae447e38908ed808bd02d3f645c475639312f080fbb83d7822e43") # Секретный ключ для webhook URL
    
    # Опциональные переменные с значениями по умолчанию
    webhook_base_url: str = "https://your-service-name.onrender.com"  # Будет меняться
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
