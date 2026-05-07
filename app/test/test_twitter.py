import pytest
import hashlib
import io
from sqlalchemy import select
from app.database.models import (
    Tweet,
    Like,
    Followers,
    Content,
    Tweet_and_Content,
)


@pytest.mark.users
@pytest.mark.asyncio
async def test_get_user_info(client, test_user, denis_user):
    """Тест успешного получения информации о пользователе"""

    response = await client.get(
        f"/api/users/{denis_user.id}", headers={"api-key": test_user.api_key}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["result"] is True
    assert data["user"]["name"] == "Denis"
    assert data["user"]["id"] == denis_user.id


@pytest.mark.users
@pytest.mark.asyncio
async def test_get_fake_user_info(client, test_user):
    """Тест получения инфы о несуществующем пользователе"""
    fake_id = 5
    response = await client.get(
        f"/api/users/{fake_id}", headers={"api-key": test_user.api_key}
    )

    assert response.status_code == 404

    data = response.json()
    assert data["result"] is False
    expected_error = f"User {fake_id} not found"
    assert expected_error == data["error_message"]


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_write_tweet(client, test_user, db_session):
    """Тест написания поста"""
    user_data = {"tweet_data": "abracadabra"}

    response = await client.post(
        f"/api/tweets", json=user_data, headers={"api-key": test_user.api_key}
    )

    assert response.status_code == 201

    data = response.json()
    assert data["result"] is True
    assert "tweet_id" in data

    tweet = await db_session.execute(
        select(Tweet).where(Tweet.author_id == test_user.id)
    )
    tweet_result = tweet.scalar_one_or_none()

    assert tweet_result.author_id == test_user.id


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_delete_tweet(client, created_tweet_id, db_session, test_user):
    """Тест удаления поста"""
    delete_query = await client.delete(
        f"/api/tweets/{created_tweet_id}", headers={"api-key": test_user.api_key}
    )

    assert delete_query.status_code == 200

    # проверяем, что его нет в БД
    delete_query = await db_session.execute(
        select(Tweet).where(
            Tweet.id == created_tweet_id, Tweet.author_id == test_user.id
        )
    )
    db_content = delete_query.scalar_one_or_none()

    assert db_content is None


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_delete_fake_tweet(client, test_user):
    """Тест удаления несуществующего поста"""
    fake_tweet_id = 5

    delete_query = await client.delete(
        f"/api/tweets/{fake_tweet_id}", headers={"api-key": test_user.api_key}
    )

    assert delete_query.status_code == 404

    error_data = delete_query.json()
    expected_error = f"Tweet {fake_tweet_id} not found or you are not the author"
    assert expected_error == error_data["error_message"]


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_delete_wrong_tweet(client, created_tweet_id, denis_user):
    """Тест того, что нельзя удалить не свой пост"""
    delete_query = await client.delete(
        f"/api/tweets/{created_tweet_id}", headers={"api-key": denis_user.api_key}
    )

    assert delete_query.status_code == 404

    error_data = delete_query.json()
    expected_error = f"Tweet {created_tweet_id} not found or you are not the author"
    assert expected_error == error_data["error_message"]


@pytest.mark.images
@pytest.mark.asyncio
async def test_upload_media_success(client, test_user, db_session):
    """Тест успешной загрузки изображения"""
    # Готовим фейковый файл
    file_name = "test_image.png"
    file_content = b"fake-image-binary-content"
    file_hash = hashlib.sha256(file_content).hexdigest()

    # Оборачиваем байты в файлоподобный объект
    file_obj = io.BytesIO(file_content)

    response = await client.post(
        "/api/medias",
        headers={"api-key": test_user.api_key},
        files={"file": (file_name, file_obj, "image/png")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "media_id" in data
    media_id = data["media_id"]

    result = await db_session.execute(select(Content).where(Content.id == media_id))
    db_content = result.scalar_one_or_none()

    assert db_content is not None
    assert db_content.content_name == file_name
    assert db_content.content_hash == file_hash
    assert db_content.file_body == file_content
    assert db_content.user_id == test_user.id


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_upload_wrong_image(client, test_user, denis_user, db_session):
    """Тест, что юзер А не может написать пост с фото, загруженное пользователем Б"""

    # Юзер test загружает фото
    file_name = "test_image.png"
    file_content = b"fake-image-binary-content"
    file_hash = hashlib.sha256(file_content).hexdigest()
    file_obj = io.BytesIO(file_content)

    post_meadia_response = await client.post(
        "/api/medias",
        headers={"api-key": test_user.api_key},
        files={"file": (file_name, file_obj, "image/png")},
    )

    assert post_meadia_response.status_code == 201
    post_meadia_data = post_meadia_response.json()
    assert "media_id" in post_meadia_data
    media_id = post_meadia_data["media_id"]

    # Проверяем сохранение в базе данных
    query = select(Content).where(Content.id == media_id)
    result = await db_session.execute(query)
    db_content = result.scalar_one_or_none()

    assert db_content is not None
    assert db_content.content_name == file_name
    assert db_content.content_hash == file_hash
    assert db_content.file_body == file_content
    assert db_content.user_id == test_user.id

    # Юзер Denis пытается загрузить фото, загруженное юзером Test
    user_data = {"tweet_data": "abracadabra", "tweet_media_ids": [db_content.id]}

    error_response = await client.post(
        f"/api/tweets", json=user_data, headers={"api-key": denis_user.api_key}
    )
    error_data = error_response.json()
    assert error_response.status_code == 404

    error_data = error_response.json()
    expected_error = "Media not found"
    assert expected_error == error_data["error_message"]


@pytest.mark.images
@pytest.mark.asyncio
async def test_upload_media_too_large(client, test_user):
    """Загрузка файла размером более 5 МБ"""
    # Создаем контент размером чуть больше 5 МБ
    too_large_content = b"0" * (5 * 1024 * 1024 + 1)
    file_obj = io.BytesIO(too_large_content)

    response = await client.post(
        "/api/medias",
        headers={"api-key": test_user.api_key},
        files={"file": ("too_big.png", file_obj, "image/png")},
    )

    assert response.status_code == 404
    error_data = response.json()

    expected_msg = "Too big size (max 5 MB)"
    assert error_data["error_message"] == expected_msg


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_write_tweet_with_media(client, test_user, db_session):
    """Тест написания поста с фото"""
    # загружаем фото
    file_name = "test_image.png"
    file_content = b"fake-image-binary-content"

    file_obj = io.BytesIO(file_content)

    meadia_response = await client.post(
        "/api/medias",
        headers={"api-key": test_user.api_key},
        files={"file": (file_name, file_obj, "image/png")},
    )

    assert meadia_response.status_code == 201

    media_query = await db_session.execute(
        select(Content).where(
            Content.content_name == file_name,
            Content.file_body == file_content,
            Content.user_id == test_user.id,
        )
    )

    media_result = media_query.scalar_one_or_none()
    assert media_result is not None

    # пишем пост с этим фото
    user_data = {"tweet_data": "abracadabra", "tweet_media_ids": [media_result.id]}

    response = await client.post(
        f"/api/tweets", json=user_data, headers={"api-key": test_user.api_key}
    )
    data = response.json()
    assert data["result"] is True
    assert "tweet_id" in data

    # проверяем, что создался пост в БД
    new_tweet_id = data["tweet_id"]
    tweet_query = await db_session.execute(
        select(Tweet).where(Tweet.id == new_tweet_id)
    )
    db_tweet = tweet_query.scalar_one_or_none()

    assert db_tweet is not None
    # проверяем, что автор поста — test
    assert db_tweet.author_id == test_user.id

    # проверяем образовавшуюся связь
    link_query = await db_session.execute(
        select(Tweet_and_Content).where(
            Tweet_and_Content.tweet_id == new_tweet_id,
            Tweet_and_Content.content_id == media_result.id,
        )
    )
    link_record = link_query.first()
    assert link_record is not None


@pytest.mark.follow
@pytest.mark.asyncio
async def test_follow_user(client, test_user, denis_user, db_session):
    """Тест подписки на пользователя"""
    response = await client.post(
        f"/api/users/{denis_user.id}/follow", headers={"api-key": test_user.api_key}
    )
    assert response.status_code == 201
    data = response.json()

    assert data["result"] is True

    follow_query = await db_session.execute(
        select(Followers).where(
            Followers.follower_id == test_user.id,
            Followers.followed_id == denis_user.id,
        )
    )
    follow_result = follow_query.first()
    assert follow_result is not None


@pytest.mark.follow
@pytest.mark.asyncio
async def test_follow_fake_user(client, test_user, db_session):
    """Тест подписки на несуществующего пользователя"""
    fake_user_id = 5
    response = await client.post(
        f"/api/users/{fake_user_id}/follow", headers={"api-key": test_user.api_key}
    )
    assert response.status_code == 404

    error_data = response.json()
    expected_error = f"User {fake_user_id} id not found"
    assert expected_error == error_data["error_message"]


@pytest.mark.follow
@pytest.mark.asyncio
async def test_stop_following_user(client, test_user, denis_user, db_session):
    """Тест отписки на пользователя"""
    response = await client.post(
        f"/api/users/{denis_user.id}/follow", headers={"api-key": test_user.api_key}
    )
    assert response.status_code == 201

    # првоеряем создание связи
    follow_query = await db_session.execute(
        select(Followers).where(
            Followers.follower_id == test_user.id,
            Followers.followed_id == denis_user.id,
        )
    )
    follow_result = follow_query.first()
    assert follow_result is not None

    # теперь отписываемся
    delete_response = await client.delete(
        f"/api/users/{denis_user.id}/follow", headers={"api-key": test_user.api_key}
    )
    assert delete_response.status_code == 200
    # проверяем, что связь удалилась
    unfollow_query = await db_session.execute(
        select(Followers).where(
            Followers.follower_id == test_user.id,
            Followers.followed_id == denis_user.id,
        )
    )
    follow_result = unfollow_query.first()
    assert follow_result is None


@pytest.mark.follow
@pytest.mark.asyncio
async def test_stop_following_fake_user(client, test_user, denis_user, db_session):
    """Тест отписки от несуществующего пользователя"""
    fake_user_id = 5
    delete_response = await client.delete(
        f"/api/users/{fake_user_id}/follow", headers={"api-key": test_user.api_key}
    )
    assert delete_response.status_code == 404

    error_data = delete_response.json()
    expected_error = f"Follower {fake_user_id} not found"
    assert expected_error == error_data["error_message"]


@pytest.mark.users
@pytest.mark.asyncio
async def test_get_me(client, test_user):
    """Тест получения основной инфы о самом себе
    Юзер сам смотрит свой профиль"""
    response = await client.get(
        f"/api/users/me", headers={"api-key": test_user.api_key}
    )
    assert response.status_code == 200

    data = response.json()

    assert data["user"]["id"] == test_user.id
    assert data["user"]["name"] == test_user.name


@pytest.mark.users
@pytest.mark.asyncio
async def test_get_me_with_followers(client, test_user, denis_user, db_session):
    """Тест отображения подписок и подписчиков в своем профиле"""
    # test подписывается на Denis
    test_response = await client.post(
        f"/api/users/{denis_user.id}/follow", headers={"api-key": test_user.api_key}
    )
    assert test_response.status_code == 201
    test_data = test_response.json()

    assert test_data["result"] is True

    follow_test_query = await db_session.execute(
        select(Followers).where(
            Followers.follower_id == test_user.id,
            Followers.followed_id == denis_user.id,
        )
    )
    # проверям, что связь создалась
    follow_test_result = follow_test_query.first()
    assert follow_test_result is not None

    # теперь смотрим на профиль
    profile_test_response = await client.get(
        f"/api/users/me", headers={"api-key": test_user.api_key}
    )
    assert profile_test_response.status_code == 200

    data = profile_test_response.json()

    assert data["user"]["id"] == test_user.id
    assert data["user"]["name"] == test_user.name
    assert data["user"]["following"][0]["name"] == denis_user.name
    assert data["user"]["following"][0]["id"] == denis_user.id

    # теперь Denis подписывается на test
    denis_response = await client.post(
        f"/api/users/{test_user.id}/follow", headers={"api-key": denis_user.api_key}
    )
    assert denis_response.status_code == 201
    denis_data = denis_response.json()

    assert denis_data["result"] is True

    follow_denis_query = await db_session.execute(
        select(Followers).where(
            Followers.follower_id == denis_user.id,
            Followers.followed_id == test_user.id,
        )
    )
    # проверям, что связь создалась
    follow_denis_result = follow_denis_query.first()
    assert follow_denis_result is not None

    await db_session.refresh(test_user)
    # теперь у test должен появиться в followers - Denis
    profile_test_with_denis_response = await client.get(
        f"/api/users/me", headers={"api-key": test_user.api_key}
    )
    assert profile_test_with_denis_response.status_code == 200

    test_with_denis_data = profile_test_with_denis_response.json()

    assert test_with_denis_data["user"]["followers"][0]["name"] == denis_user.name
    assert test_with_denis_data["user"]["followers"][0]["id"] == denis_user.id
    # проверям что не слетела подписка
    assert data["user"]["following"][0]["name"] == denis_user.name
    assert data["user"]["following"][0]["id"] == denis_user.id


@pytest.mark.likes
@pytest.mark.asyncio
async def test_like(client, denis_user, created_tweet_id, db_session):
    """Тест лайка на пост"""

    like_response = await client.post(
        f"/api/tweets/{created_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )
    like_data = like_response.json()
    assert like_data["result"] is True

    # проверяем в БД
    find_like = await db_session.execute(
        select(Like).where(
            Like.user_id == denis_user.id, Like.tweet_id == created_tweet_id
        )
    )
    find_like_result = find_like.scalar_one_or_none()
    assert find_like_result is not None


@pytest.mark.likes
@pytest.mark.asyncio
async def test_like_fake_tweet(client, denis_user, db_session):
    """Тест лайка на несуществующий пост"""
    fake_tweet_id = 5

    like_response = await client.post(
        f"api/tweets/{fake_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )
    assert like_response.status_code == 404

    error_data = like_response.json()
    expected_error = "Tweet not found"
    assert expected_error == error_data["error_message"]

    # проверяем в БД
    find_like = await db_session.execute(
        select(Like).where(
            Like.user_id == denis_user.id, Like.tweet_id == fake_tweet_id
        )
    )
    find_like_result = find_like.scalar_one_or_none()
    assert find_like_result is None


@pytest.mark.likes
@pytest.mark.asyncio
async def test_double_like_tweet(client, created_tweet_id, denis_user, db_session):
    """Тест невозможности двойного лайка"""

    like_response = await client.post(
        f"api/tweets/{created_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )
    assert like_response.status_code == 201

    like_again_response = await client.post(
        f"api/tweets/{created_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )

    assert like_again_response.status_code == 404

    error_data = like_again_response.json()
    expected_error = f"There is already like on post{created_tweet_id}"
    assert expected_error == error_data["error_message"]

    # проверяем в БД
    find_like = await db_session.execute(
        select(Like).where(
            Like.user_id == denis_user.id, Like.tweet_id == created_tweet_id
        )
    )
    find_like_result = find_like.scalar_one()
    assert find_like_result is not None


@pytest.mark.likes
@pytest.mark.asyncio
async def test_delete_like(client, created_tweet_id, test_user, denis_user, db_session):
    """Тест удаления лайка"""
    like_response = await client.post(
        f"api/tweets/{created_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )
    like_data = like_response.json()
    assert like_data["result"] is True

    # проверяем в БД
    find_like = await db_session.execute(
        select(Like).where(
            Like.user_id == denis_user.id, Like.tweet_id == created_tweet_id
        )
    )
    find_like_result = find_like.scalar_one_or_none()
    assert find_like_result is not None

    # юзер Denis удаляет лайк
    delete_like = await client.delete(
        f"/api/tweets/{created_tweet_id}/likes", headers={"api-key": denis_user.api_key}
    )

    delete_like_data = delete_like.json()
    assert delete_like_data["result"] is True

    # проверяем в БД
    find_like = await db_session.execute(
        select(Like).where(
            Like.user_id == denis_user.id, Like.tweet_id == created_tweet_id
        )
    )
    find_like_result = find_like.scalar_one_or_none()
    assert find_like_result is None


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_get_all_tweets_complex(client, test_user, denis_user, db_session):
    """Тест получения ленты со всеми вложенными данными: автор, лайки, вложения"""

    # Создаем медиа
    content = Content(
        content_name="img.png",
        content_hash="hash",
        user_id=test_user.id,
        file_body=b"123",
    )
    db_session.add(content)
    await db_session.flush()

    # Создаем твит
    tweet = Tweet(content="Full stack tweet", author_id=test_user.id)
    db_session.add(tweet)
    await db_session.flush()

    # Добавляем лайк от Denis
    like = Like(user_id=denis_user.id, tweet_id=tweet.id)
    db_session.add(like)

    # Добавляем вложение
    link = Tweet_and_Content(tweet_id=tweet.id, content_id=content.id)
    db_session.add(link)

    await db_session.commit()

    response = await client.get("/api/tweets", headers={"api-key": test_user.api_key})

    assert response.status_code == 200
    data = response.json()
    assert "tweets" in data
    assert len(data["tweets"]) > 0

    target_tweet = data["tweets"][0]
    assert target_tweet["content"] == "Full stack tweet"
    assert target_tweet["author"]["name"] == test_user.name
    assert len(target_tweet["likes"]) == 1
    assert target_tweet["likes"][0]["name"] == "Denis"

    expected_link = f"/api/medias/{content.id}"
    assert expected_link in target_tweet["attachments"]


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_get_all_tweets_without_photos(client, test_user, denis_user, db_session):
    """Тест получения ленты с постами без вложений"""

    # создаем твит
    fake_text_1 = "Tweet with no photo"
    tweet_1 = Tweet(content=fake_text_1, author_id=test_user.id)
    db_session.add(tweet_1)
    await db_session.flush()

    # создадим еще один твит от другого пользователя
    fake_text_2 = "Again no photo"
    tweet_2 = Tweet(content=fake_text_2, author_id=denis_user.id)
    db_session.add(tweet_2)
    await db_session.flush()

    # Добавляем лайк от Denis
    like = Like(user_id=denis_user.id, tweet_id=tweet_1.id)
    db_session.add(like)

    await db_session.commit()

    response = await client.get("/api/tweets", headers={"api-key": test_user.api_key})

    assert response.status_code == 200
    data = response.json()
    assert "tweets" in data
    assert len(data["tweets"]) == 2

    target_tweet_1 = data["tweets"][1]
    assert target_tweet_1["content"] == fake_text_1
    assert target_tweet_1["author"]["name"] == test_user.name
    assert len(target_tweet_1["likes"]) == 1
    assert target_tweet_1["likes"][0]["name"] == "Denis"
    assert target_tweet_1["attachments"] == []

    target_tweet_2 = data["tweets"][0]
    assert target_tweet_2["content"] == fake_text_2
    assert target_tweet_2["author"]["name"] == denis_user.name
    assert len(target_tweet_2["likes"]) == 0
    assert target_tweet_2["attachments"] == []


@pytest.mark.tweets
@pytest.mark.asyncio
async def test_get_empty_tweets(client, test_user):
    """Тест получения пустой ленты"""

    response = await client.get("/api/tweets", headers={"api-key": test_user.api_key})

    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert len(data["tweets"]) == 0
    assert data["tweets"] == []
