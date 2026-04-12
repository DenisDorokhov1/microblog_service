from sqlalchemy import Column, Integer, String, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


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
        "Content", back_populates="tweet", cascade="all, delete-orphan"
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
    __tablename__ = "content"
    id = Column(Integer, primary_key=True, index=True)
    content_name = Column(String)
    tweet_id = Column(
        Integer, ForeignKey("tweets.id", ondelete="CASCADE"), nullable=True
    )

    tweet = relationship("Tweet", back_populates="attachments")
