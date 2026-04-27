import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from routes import app
from database.init_database import Base, get_session


TEST_DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5433/microblog_test_db"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=True,
)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_db():
    from database import models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def session():
    """Фикстура для работы с БД в тестах"""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(session):
    """Клиент для запросов к API с подмененной базой"""

    def override_get_session():
        yield session

    # подменяем реальную сессию на тестовую
    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def create_user(session):
    """Фабрика для создания любого количества пользователей"""

    from database.models import User

    async def _create_user(name: str, api_key: str):
        user = User(name=name, api_key=api_key)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return _create_user
