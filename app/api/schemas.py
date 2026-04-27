from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class UserShort(BaseModel):
    """Короткая инфа про пользователя"""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserProfileOut(UserShort):
    """Полная инфа для профиля"""

    followers: List[UserShort] = []
    following: List[UserShort] = []

    model_config = ConfigDict(from_attributes=True)


class TweetOut(BaseModel):
    """Схема для отображения твита"""

    id: int
    content: str
    author: UserShort
    likes: List[UserShort] = []
    attachments: List[str] = []

    # берет объекты типов данных как атрибуты
    model_config = ConfigDict(from_attributes=True)


class TweetIn(BaseModel):
    """Схема для создания нового твита"""

    tweet_data: str = Field(..., max_length=500, description="Текст твита")
    tweet_media_ids: Optional[List[int]] = Field(
        default=[], description="ID загруженных медиафайлов"
    )


class SuccessResponse(BaseModel):
    result: bool = True


class SuccessTweet(SuccessResponse):
    tweet_id: int


class SuccessMedia(SuccessResponse):
    media_id: int


class ProfileResponse(SuccessResponse):
    user: UserProfileOut


class TweetsListResponse(SuccessResponse):
    tweets: List[TweetOut]


class TweetCreateResponse(SuccessResponse):
    tweet_id: int


class ErrorResponse(BaseModel):
    result: bool = False
    error_type: str
    error_message: str
