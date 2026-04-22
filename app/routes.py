from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Response,
    Request,
    Response,
    UploadFile,
    File,
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

# ниже раскоментировать, если проверка локально
# from api.dependencies import get_current_user
# from api.schemas import *
from app.api.dependencies import get_current_user
from app.api.schemas import *
from app.database.models import *
from app.database.init_database import engine, session, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/api/users/me", response_model=ProfileResponse)
async def get_me(user: User = Depends(get_current_user)) -> ProfileResponse:
    """Основаная инфа про самого юзера"""
    result = await session.execute(
        select(User)
        .options(selectinload(User.followers), selectinload(User.following))
        .where(User.id == user.id)
    )
    full_user = result.scalars().first()

    return ProfileResponse(user=full_user)


@app.post("/api/tweets", response_model=SuccessTweet)
async def create_tweet(
    tweet: TweetIn,
    user: User = Depends(get_current_user),
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

    result = SuccessTweet(tweet_id=new_tweet.id)

    return result


@app.post("/api/medias", status_code=201)
async def upload_media(
    file: UploadFile = File(...), user: User = Depends(get_current_user)
):
    """Загрузить контент (файлы) для твитов"""
    # читаем бинарное содержимое файла
    file_data = await file.read()

    # проверка размера, не больше 5МБ
    if len(file_data) > 5 * 1024 * 1024:
        error = ErrorResponse(error_type="404", error_message="Too big size (max 5 GB)")
        raise HTTPException(status_code=404, detail=error.model_dump())

    # Создаем запись в базе
    new_media = Content(
        file_body=file_data, content_name=file.filename, user_id=user.id
    )

    session.add(new_media)

    # Сбрасываем изменения, чтобы БД присвоила ID, но пока не закрываем транзакцию окончательно
    await session.commit()

    result = SuccessMedia(media_id=new_media.id)
    return result


@app.get("/api/medias/{media_id}", tags=["medias"])
async def get_media(
    media_id: int,
):
    # Ищем контент в таблице Content
    result = await session.execute(select(Content).where(Content.id == media_id))
    media = result.scalars().first()

    if not media:
        raise HTTPException(status_code=404, detail="File not found")

    # Отправляем бинарные данные
    return Response(content=media.file_body, media_type="image/png")


@app.get("/api/tweets", status_code=200)
async def get_all_tweets(user: User = Depends(get_current_user)) -> TweetsListResponse:
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
    for t in all_tweets:
        # генерируем относительные ссылки
        links = [
            f"/api/medias/{tac.content.id}" for tac in t.attachments if tac.content
        ]

        likes_out = [UserShort.model_validate(like.user) for like in t.tweet_likes]
        # превращает "объекты Python/БД" в "Pydantic-модели для JSON".
        tweets_out.append(
            TweetOut(
                id=t.id,
                content=t.content,
                author=UserShort.model_validate(t.author),
                likes=likes_out,
                attachments=links,
            )
        )

    return TweetsListResponse(tweets=tweets_out)


@app.post("/api/tweets/{tweet_id}/likes", status_code=201)
async def post_like(tweet_id: int, user: User = Depends(get_current_user)):
    """Поставить лайк на пост"""
    # проверяем существование твита
    result = await session.execute(select(Tweet).where(Tweet.id == tweet_id))
    tweet = result.scalars().first()
    if not tweet:
        raise HTTPException(status_code=404, detail="Твит не найден")

    # ставим лайк
    new_like = Like(user_id=user.id, tweet_id=tweet.id)
    session.add(new_like)
    await session.commit()

    return SuccessResponse()


@app.delete("/api/tweets/{tweet_id}/likes", status_code=200)
async def delete_like(tweet_id: int, user: User = Depends(get_current_user)):
    """Удалить лайк с поста"""
    # ищем такой пост в БД
    result = await session.execute(
        select(Like).where(Like.tweet_id == tweet_id, Like.user_id == user.id)
    )
    like_to_delete = result.scalars().first()

    if not like_to_delete:
        raise HTTPException(status_code=404, detail=f"Tweet {tweet_id} id not found")

    session.delete(like_to_delete)
    await session.commit()

    return SuccessResponse()


@app.post("/api/users/{user_id}/follow", status_code=201)
async def follow_user(user_id: int, user: User = Depends(get_current_user)):
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


@app.get("/api/users/{user_id}", status_code=200)
async def get_user(user_id: int, user: User = Depends(get_current_user)):
    # ищем в БД юзера
    result = await session.execute(
        select(User)
        .options(selectinload(User.followers), selectinload(User.following))
        .where(User.id == user_id)
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    full_user = result.scalars().first()

    return ProfileResponse(user=full_user)


# из корня проекта
# python3 -m uvicorn app.routes:app --reload
# uvicorn routes:app --reload
