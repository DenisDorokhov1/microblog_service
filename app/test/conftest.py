import pytest
import asyncio
from sqlalchemy import select
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.routes import app
from app.database.init_database import Base, get_session
from app.database.models import User

TEST_DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5433/microblog_test_db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)

AsyncTestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def prepare_database(event_loop):
    async def init_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # создаём пользователя один раз
        async with AsyncTestingSessionLocal() as session:
            users_data = [
                {"name": "Test", "api_key": "test"},
                {"name": "Denis", "api_key": "denis"},
            ]
            for i_user in users_data:
                result = await session.execute(
                    select(User).where(User.api_key == i_user["api_key"])
                )
                user = result.scalars().first()

                if not user:
                    session.add(User(**i_user))

            await session.commit()

    async def drop_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    event_loop.run_until_complete(init_models())
    yield
    event_loop.run_until_complete(drop_models())


@pytest.fixture()
async def db_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncTestingSessionLocal(bind=connection)

        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture()
async def client(db_session):

    async def override_get_session():
        # Вместо новой сессии отдаем ту же, что и в коде теста
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture()
async def test_user(db_session):
    result = await db_session.execute(select(User).where(User.api_key == "test"))
    return result.scalars().first()


@pytest.fixture()
async def denis_user(db_session):
    result = await db_session.execute(select(User).where(User.api_key == "denis"))
    return result.scalars().first()


@pytest.fixture
async def created_tweet_id(client, test_user):
    """Создает твит и возвращает его ID"""
    user_data = {"tweet_data": "abracadabra"}
    response = await client.post(
        "/api/tweets", json=user_data, headers={"api-key": test_user.api_key}
    )
    return response.json()["tweet_id"]


# для тестов запустить контейнер для БД
# docker-compose -f docker-compose.test.yaml up -d
