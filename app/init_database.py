import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from database.base import Base
from database import models

# пока что вынес создание таблицы сюда, потом перенесу в другое место

DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/microblog_db"
engine = create_async_engine(DATABASE_URL, echo=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
