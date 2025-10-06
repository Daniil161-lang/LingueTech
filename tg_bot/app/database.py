from sqlalchemy import MetaData, Table, Column, BigInteger, String, Boolean, create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Используем SQLAlchemy Core для более легковесного подхода
metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("user_id", BigInteger, unique=True, nullable=False),
    Column("username", String),
    Column("first_name", String),
    Column("is_subscribed", Boolean, default=False),
)

# Создаем движок. Render использует SSL, поэтому добавляем соответствующие аргументы
engine = create_engine(
    settings.database_url,
    echo=False,  # Не включать в продакшене для производительности
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=300,  # Переподключение каждые 300 секунд
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация базы данных, создание таблиц."""
    try:
        metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise