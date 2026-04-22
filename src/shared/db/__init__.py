from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base para todos os modelos SQLAlchemy do projeto."""
    pass


def make_engine(database_url: str):
    """Cria o engine async sob demanda — nunca no import."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Dependency do FastAPI — injeta sessão e garante fechamento."""
    async with session_factory() as session:
        yield session