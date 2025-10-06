import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Обязательно объявите ВСЕ используемые переменные как поля класса.
    bot_token: str
    channel_username: str
    database_url: str
    webhook_secret: str
    # Убедитесь, что имя поля совпадает с именем переменной окружения.
    # Если в Render переменная называется WEBHOOK_BASE_URL, то и поле должно называться так же.
    webhook_base_url: str = "https://your-service-name.onrender.com"  # Можно задать значение по умолчанию
    model_config = SettingsConfigDict(extra="allow")
    class Config:
        # Если хотите, чтобы Pydantic автоматически игнорировал лишние переменные,
        # раскомментируйте строку ниже. Но лучше привести модель в соответствие.
        # extra = 'ignore'
        env_file = ".env"

settings = Settings()
