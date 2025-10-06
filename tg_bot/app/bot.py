from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from sqlalchemy.orm import Session
from app.database import users, get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class BotService:
    def __init__(self, token: str):
        self.application = (
            Application.builder()
            .token(token)
            .post_init(self._post_init)
            .build()
        )
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрация всех обработчиков команд и callback'ов."""
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CallbackQueryHandler(self._button_handler))
    
    async def _post_init(self, app: Application):
        """Действия после инициализации бота."""
        logger.info("Bot is initializing...")
        # Webhook будет устанавливаться в main.py
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start."""
        user = update.effective_user
        db = next(get_db())
        
        # Добавляем/обновляем пользователя в БД
        try:
            insert_stmt = users.insert().values(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name
            ).on_conflict_do_update(
                index_elements=[users.c.user_id],
                set_={
                    'username': user.username,
                    'first_name': user.first_name
                }
            )
            db.execute(insert_stmt)
            db.commit()
        except Exception as e:
            logger.error(f"Database error for user {user.id}: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Создаем инлайн-кнопку
        keyboard = [[InlineKeyboardButton("🎁 Получить материалы", callback_data="get_materials")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n"
            "Я бот для рассылки полезных материалов. Нажми на кнопку ниже, чтобы получить бесплатные материалы."
        )
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на инлайн-кнопки."""
        query = update.callback_query
        await query.answer()  # Подтверждаем нажатие
        user = update.effective_user
        
        if query.data == "get_materials":
            # В продакшене лучше вынести в отдельный метод или dependency
            try:
                chat_member = await self.application.bot.get_chat_member(
                    chat_id=settings.channel_username,
                    user_id=user.id
                )
                is_subscribed = chat_member.status in ["member", "administrator", "creator"]
                
                if is_subscribed:
                    materials_text = (
                        "Спасибо за подписку! Вот твои материалы:\n\n"
                        "📚 Полезные ссылки:\n"
                        "• Книга по Python: [ссылка]\n"
                        "• Видеоуроки: [ссылка]\n"
                        "• Чек-лист: [ссылка]\n\n"
                        "Приятного обучения! 🚀"
                    )
                    await query.edit_message_text(text=materials_text)
                else:
                    not_subscribed_text = (
                        "Для получения материалов необходимо подписаться на наш канал.\n"
                        f"Подпишись здесь: {settings.channel_username}\n\n"
                        "После подписки нажми на кнопку снова!"
                    )
                    await query.edit_message_text(text=not_subscribed_text)
                    
            except Exception as e:
                logger.error(f"Error checking subscription for user {user.id}: {e}")
                await query.edit_message_text(
                    text="⚠️ Произошла ошибка при проверке подписки. Пожалуйста, попробуйте позже."
                )
    
    async def process_update(self, update: Update):
        """Основной метод для обработки входящих обновлений от webhook."""
        await self.application.process_update(update)

# Глобальный экземпляр сервиса бота
bot_service = None

def get_bot_service() -> BotService:
    """Получение глобального экземпляра сервиса бота (синглтон)."""
    global bot_service
    if bot_service is None:
        bot_service = BotService(settings.bot_token)
    return bot_service