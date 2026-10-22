"""Команды CQRS для сообщений обсуждений."""

from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetTopicPostsCommand(Command):
    """Страница корневых сообщений темы."""

    topic_id: int
    page: int = 1
    page_size: int | None = None
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class GetPostRepliesCommand(Command):
    """Страница прямых ответов на сообщение."""

    post_id: int
    page: int = 1
    page_size: int | None = None
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class CreateTopicPostCommand(Command):
    """Создать корневое сообщение в теме."""

    topic_id: int
    author_id: uuid.UUID
    body: str
    quoted_post_id: int | None = None
    is_admin: bool = False


@dataclass
class CreateReplyCommand(Command):
    """Создать ответ на корневое сообщение."""

    parent_post_id: int
    author_id: uuid.UUID
    body: str
    quoted_post_id: int | None = None
    is_admin: bool = False


@dataclass
class UpdatePostCommand(Command):
    """Отредактировать своё сообщение."""

    post_id: int
    author_id: uuid.UUID
    body: str
    quoted_post_id: int | None = None
    is_admin: bool = False
