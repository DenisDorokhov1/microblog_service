import hashlib
from fastapi import (
    FastAPI,
    Depends,
    Response,
    Request,
    UploadFile,
    File,
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from contextlib import asynccontextmanager
from sqlalchemy import delete
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# ниже раскоментировать, если проверка локально
# from api.dependencies import get_current_user
# from api.schemas import *
from app.api.dependencies import get_current_user
from app.api.schemas import (
    UserShort,
    TweetOut,
    TweetIn,
    SuccessResponse,
    SuccessTweet,
    SuccessMedia,
    ProfileResponse,
    TweetsListResponse,
    ErrorResponse,
)
from app.database.models import (
    User,
    Tweet,
    Like,
    Followers,
    Content,
    Tweet_and_Content,
)
from app.database.init_database import engine, Base, get_session


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    session: AsyncSession = Depends(get_session),
):
    """Действия при запуске приложения"""
    async with engine.begin() as conn:
        # Создаем таблицы, если их нет
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Действия при выключении (SHUTDOWN)
    await session.close()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Кастомный обработчик для HTTPException"""
    # Если в detail лежит словарь, разворачиваем его
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )

    # Для стандартных ошибок FastAPI (где detail — строка)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "result": False,
            "error_type": str(exc.status_code),
            "error_message": exc.detail,
        },
    )


# не нашел во фронтенде, где это вообще
@app.get("/api/users/me", status_code=200)
async def get_me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> ProfileResponse:
    """Основаная инфа про самого юзера"""
    result = await session.execute(
        select(User)
        .options(selectinload(User.followers), selectinload(User.following))
        .where(User.id == user.id)
    )
    full_user = result.scalars().first()

    return ProfileResponse(user=full_user)


@app.post("/api/tweets", status_code=201)
async def create_tweet(
    tweet: TweetIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessTweet:
    """Написать пост"""
    tweet_data = tweet.model_dump()
    # Убираем медиа-ID, так как в модели Tweet нет такого поля
    media_ids = tweet_data.pop("tweet_media_ids", [])

    new_tweet = Tweet(content=tweet_data["tweet_data"], author_id=user.id)

    session.add(new_tweet)
    await session.flush()

    if media_ids:
        # Ищем картинки в БД у опредленного юзера
        query = select(Content).where(
            Content.id.in_(media_ids), Content.user_id == user.id
        )
        result = await session.execute(query)
        contents = result.scalars().all()

        # Проверка, все ли присланные ID существуют
        if len(contents) != len(media_ids):
            error = ErrorResponse(error_type="404", error_message="Media not found")
            raise HTTPException(status_code=404, detail=error.model_dump())

        # Создаю связи
        for content_obj in contents:
            attachment_link = Tweet_and_Content(tweet=new_tweet, content=content_obj)
            session.add(attachment_link)
    await session.commit()
    await session.refresh(new_tweet)

    return SuccessTweet(tweet_id=new_tweet.id)


@app.delete("/api/tweets/{tweet_id}", status_code=200)
async def delete_tweet(
    tweet_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    """Удалить твит"""
    # Прямой запрос на удаление
    query = (
        delete(Tweet)
        .where(Tweet.id == tweet_id, Tweet.author_id == user.id)
        .returning(Tweet.id)
    )

    result = await session.execute(query)
    tweet_to_delete = result.scalar_one_or_none()

    if not tweet_to_delete:
        await session.rollback()
        raise HTTPException(
            status_code=404,
            detail=f"Tweet {tweet_id} not found or you are not the author",
        )

    await session.commit()
    return SuccessResponse()


@app.post("/api/medias", status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessMedia:
    """Загрузить контент (файлы) для твитов"""
    # читаем бинарное содержимое файла
    file_data = await file.read()

    # проверка размера, не больше 5МБ
    if len(file_data) > 5 * 1024 * 1024:
        error = ErrorResponse(error_type="404", error_message="Too big size (max 5 MB)")
        raise HTTPException(status_code=404, detail=error.model_dump())

    # Считаем хеш файла
    file_hash = hashlib.sha256(file_data).hexdigest()

    # Создаем запись в базе
    new_media = Content(
        file_body=file_data,
        content_name=file.filename,
        content_hash=file_hash,
        user_id=user.id,
    )

    session.add(new_media)

    # Сбрасываем изменения, чтобы БД присвоила ID, но пока не закрываем транзакцию окончательно
    await session.commit()

    return SuccessMedia(media_id=new_media.id)


@app.get("/api/medias/{media_id}", tags=["medias"])
async def get_media(media_id: int, session: AsyncSession = Depends(get_session)):
    """Получаем медиа для дальнейшей загрузки в посте"""
    # Ищем контент в таблице Content
    result = await session.execute(select(Content).where(Content.id == media_id))
    media = result.scalars().first()

    if not media:
        raise HTTPException(status_code=404, detail="File not found")

    # Отправляем бинарные данные
    return Response(content=media.file_body, media_type="image/png")


@app.get("/api/tweets", status_code=200)
async def get_all_tweets(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> TweetsListResponse:
    """Посмотреть ленту из всех твитов"""
    query = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.tweet_likes).selectinload(Like.user),
            selectinload(Tweet.attachments).selectinload(Tweet_and_Content.content),
        )
        .order_by(Tweet.id.desc())
    )
    result = await session.execute(query)
    all_tweets = result.scalars().all()

    tweets_out = []
    for i_tweet in all_tweets:
        # генерируем относительные ссылки
        links = [
            f"/api/medias/{tac.content.id}"
            for tac in i_tweet.attachments
            if tac.content
        ]

        likes_out = [
            UserShort.model_validate(like.user) for like in i_tweet.tweet_likes
        ]
        # превращает "объекты Python/БД" в "Pydantic-модели для JSON".
        tweets_out.append(
            TweetOut(
                id=i_tweet.id,
                text=i_tweet.content,
                author=UserShort.model_validate(i_tweet.author),
                likes=likes_out,
                attachments=links,
            )
        )

    return TweetsListResponse(tweets=tweets_out)


@app.post("/api/tweets/{tweet_id}/likes", status_code=201)
async def post_like(
    tweet_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    """Поставить лайк на пост"""
    # проверяем существование твита
    result = await session.execute(select(Tweet).where(Tweet.id == tweet_id))
    tweet = result.scalars().first()
    if not tweet:
        raise HTTPException(status_code=404, detail="Tweet not found")

    # проверяем, что лайк еще не ставили на этот же пост
    like_checker = await session.execute(
        select(Like).where(Like.tweet_id == tweet_id, Like.user_id == user.id)
    )

    if like_checker.scalars().first():
        raise HTTPException(
            status_code=404, detail=f"There is already like on post{tweet_id}"
        )

    # ставим лайк
    new_like = Like(user_id=user.id, tweet_id=tweet.id)
    session.add(new_like)
    await session.commit()

    return SuccessResponse()


@app.delete("/api/tweets/{tweet_id}/likes", status_code=200)
async def delete_like(
    tweet_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    """Удалить лайк с поста"""
    query = (
        delete(Like)
        .where(Like.tweet_id == tweet_id, Like.user_id == user.id)
        .returning(Like.id)
    )

    result = await session.execute(query)
    like_to_delete = result.scalar_one_or_none()

    if not like_to_delete:
        await session.rollback()
        raise HTTPException(
            status_code=404,
            detail=f"Tweet {tweet_id} id not found",
        )

    await session.commit()
    return SuccessResponse()


@app.post("/api/users/{user_id}/follow", status_code=201)
async def follow_user(
    user_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    """Подписать на юзера"""
    # ищем такого юзера
    result = await session.execute(select(User).where(User.id == user_id))
    followed_user = result.scalars().first()

    if not followed_user:
        raise HTTPException(status_code=404, detail=f"User {user_id} id not found")
    try:
        # подписываемся на пользователя
        new_followed_user = Followers(follower_id=user.id, followed_id=followed_user.id)
        session.add(new_followed_user)
        await session.commit()
    except IntegrityError:
        # если пользователь пытается 2 раз пописать на пользователя, откатываем транзакцию
        await session.rollback()
        return SuccessResponse()

    return SuccessResponse()


@app.delete("/api/users/{user_id}/follow", status_code=200)
async def stop_following(
    user_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    "Отписаться от пользователя"
    query = (
        delete(Followers)
        .where(Followers.followed_id == user_id, Followers.follower_id == user.id)
        .returning(Followers.id)
    )

    result = await session.execute(query)
    follower_to_unsubscribe = result.scalar_one_or_none()

    if not follower_to_unsubscribe:
        await session.rollback()
        raise HTTPException(status_code=404, detail=f"Follower {user_id} not found")

    await session.commit()
    return SuccessResponse()


@app.get("/api/users/{user_id}", status_code=200)
async def get_user(
    user_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Поулчаем инфу про определенного пользователя"""
    # ищем в БД юзера
    result = await session.execute(
        select(User)
        .options(selectinload(User.followers), selectinload(User.following))
        .where(User.id == user_id)
    )

    full_user = result.scalars().first()

    if full_user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return ProfileResponse(user=full_user)


# из корня проекта
# python3 -m uvicorn app.routes:app --reload
# uvicorn routes:app --reload
