from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    LargeBinary,
)
from sqlalchemy.orm import relationship

# from database.init_database import Base

from app.database.init_database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)

    tweets = relationship(
        "Tweet", back_populates="author", cascade="all, delete-orphan"
    )

    user_likes = relationship(
        "Like", back_populates="user", cascade="all, delete-orphan"
    )

    followers = relationship(
        "User",
        secondary="followers",
        primaryjoin="User.id == Followers.followed_id",
        secondaryjoin="User.id == Followers.follower_id",
        back_populates="following",
    )

    following = relationship(
        "User",
        secondary="followers",
        primaryjoin="User.id == Followers.follower_id",
        secondaryjoin="User.id == Followers.followed_id",
        back_populates="followers",
    )


class Tweet(Base):
    __tablename__ = "tweets"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(500), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    author = relationship("User", back_populates="tweets")

    tweet_likes = relationship(
        "Like", back_populates="tweet", cascade="all, delete-orphan"
    )

    attachments = relationship(
        "Tweet_and_Content", back_populates="tweet", cascade="all, delete-orphan"
    )


class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    tweet_id = Column(Integer, ForeignKey("tweets.id", ondelete="CASCADE"))

    # создаем ограничение, 1 пользователь ставит на пост только 1 лайк
    __table_args__ = (
        UniqueConstraint("user_id", "tweet_id", name="unique_user_tweet_like"),
    )

    user = relationship("User", back_populates="user_likes")
    tweet = relationship("Tweet", back_populates="tweet_likes")


class Followers(Base):
    __tablename__ = "followers"
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    followed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    # пользователь А может подписаться на пользователя Б только 1 раз
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="unique_followers"),
    )


class Content(Base):
    __tablename__ = "contents"
    id = Column(Integer, primary_key=True, index=True)
    file_body = Column(LargeBinary, nullable=False)
    content_name = Column(String)
    content_hash = Column(String, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tweet_and_content = relationship(
        "Tweet_and_Content", back_populates="content", cascade="all, delete-orphan"
    )


class Tweet_and_Content(Base):
    __tablename__ = "tweet_and_content"
    id = Column(Integer, primary_key=True, index=True)

    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"))
    tweet_id = Column(Integer, ForeignKey("tweets.id", ondelete="CASCADE"))

    content = relationship("Content", back_populates="tweet_and_content")
    tweet = relationship("Tweet", back_populates="attachments")
