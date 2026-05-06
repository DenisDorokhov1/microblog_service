import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://admin:admin@localhost:5432/microblog_db"
)
engine = create_async_engine(DATABASE_URL, echo=True)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
session = async_session()
Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессий для зависимостей FastAPI"""
    async with async_session() as session:
        yield session


if __name__ == "__main__":
    asyncio.run(init_db())
