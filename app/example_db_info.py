import asyncio
from database.init_database import session
from database.models import User


async def seed_data():
    async with session.begin():
        test_users = [
            User(name="Nikita", api_key="nikita"),
            User(name="Vlad", api_key="vlad"),
        ]
        session.add_all(test_users)


if __name__ == "__main__":
    asyncio.run(seed_data())
