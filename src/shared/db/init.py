from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.shared.config.settings import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"ssl": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base para todos os modelos SQLAlchemy do projeto."""
    pass


async def get_db() -> AsyncSession:
    """Dependency do FastAPI — injeta sessão e garante fechamento."""
    async with AsyncSessionLocal() as session:
        yield session