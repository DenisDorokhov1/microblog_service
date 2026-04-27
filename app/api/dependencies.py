from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# from database.init_database import get_session
# from database.models import User
from app.database.init_database import get_session
from app.database.models import User
from app.api.schemas import ErrorResponse


async def get_current_user(
    api_key: str = Header(..., alias="api-key"),  # Ищем именно "api-key"
    session: AsyncSession = Depends(get_session),
) -> User:
    # Ищем пользователя с таким ключом в БД
    result = await session.execute(select(User).where(User.api_key == api_key))
    user = result.scalars().first()

    if not user:
        # Если юзер не найден, кидаем 401 по канонам API
        error_content = ErrorResponse(
            error_type="401 Unauthorized", error_message="Invalid API Key"
        ).model_dump()

        raise HTTPException(status_code=401, detail=error_content)

    return user
