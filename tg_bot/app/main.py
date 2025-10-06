from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from telegram import Update
import logging
from app.config import settings
from app.bot import get_bot_service
from app.database import init_db

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup: Инициализация БД и установка webhook
    logger.info("Starting up...")
    init_db()
    
    bot_service = get_bot_service()
    webhook_url = f"{settings.webhook_base_url}/webhook/{settings.webhook_secret}"
    
    try:
        await bot_service.application.bot.set_webhook(
            url=webhook_url,
            # Указываем только нужные типы обновлений для экономии трафика
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        # В продакшене можно отправить оповещение
    
    yield  # Здесь приложение работает
    
    # Shutdown: Удаляем webhook
    logger.info("Shutting down...")
    try:
        await bot_service.application.bot.delete_webhook()
        logger.info("Webhook deleted successfully.")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")

app = FastAPI(
    title="Production Telegram Bot",
    lifespan=lifespan,
    docs_url="/docs"  # Документация будет доступна по /docs
)

@app.get("/")
async def health_check():
    """Health check эндпоинт для мониторинга Render."""
    return {"status": "ok", "message": "Bot is running"}

@app.post("/webhook/{secret_path}")
async def process_webhook(secret_path: str, request: Request):
    """Основной эндпоинт для вебхука от Telegram."""
    # Проверяем секретный путь для безопасности
    if secret_path != settings.webhook_secret:
        raise HTTPException(status_code=404, detail="Not Found")
    
    try:
        data = await request.json()
        update = Update.de_json(data, get_bot_service().application.bot)
        await get_bot_service().process_update(update)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Эндпоинт для ручной рассылки (можно защитить дополнительной аутентификацией)
@app.post("/broadcast")
async def broadcast_message(message: str):
    """Эндпоинт для запуска рассылки (вызывается, например, через cron)."""
    # Здесь логика получения пользователей из БД и рассылки
    # Для защиты можно добавить API-ключ в заголовках
    return {"status": "Broadcast scheduled", "recipients": 0}  # Заглушка