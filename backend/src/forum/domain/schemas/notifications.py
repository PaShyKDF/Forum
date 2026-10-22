"""Схемы уведомлений о ответах и цитатах."""

from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema


class TopicNotificationItemResponse(BaseSchema):
    """Элемент списка уведомлений в header."""

    id: int = Field(..., description='ID уведомления')
    kind: str = Field(
        ...,
        description='reply или quote',
    )
    actor_uid: uuid.UUID = Field(
        ...,
        description='UID автора действия',
    )
    actor_display_name: str = Field(
        ...,
        description='Имя автора действия',
    )
    topic_id: int = Field(..., description='ID темы')
    topic_title: str = Field(..., description='Название темы')
    post_id: int = Field(
        ...,
        description='ID нового сообщения',
    )
    source_post_id: int = Field(
        ...,
        description='ID исходного сообщения',
    )
    parent_post_id: int | None = Field(
        None,
        description='ID корневого родителя, если ответ',
    )
    roots_page: int = Field(
        1,
        description='Страница корней с нужным постом',
    )
    replies_page: int | None = Field(
        None,
        description='Страница ответов, если это reply',
    )
    text: str = Field(
        ...,
        description='Текст для списка уведомлений',
    )
    created_at: datetime = Field(..., description='Время')


class TopicNotificationsListResponse(BaseSchema):
    """Список уведомлений и счётчик."""

    items: list[TopicNotificationItemResponse] = Field(
        default_factory=list,
        description='Непрочитанные уведомления',
    )
    unread_count: int = Field(
        0,
        description='Число непрочитанных',
    )


class UnreadCountResponse(BaseSchema):
    """Счётчик непрочитанных."""

    unread_count: int = Field(
        0,
        description='Число непрочитанных',
    )


class MarkChatMessagesVisibleRequest(BaseSchema):
    """Список видимых сообщений ЛС."""

    message_ids: list[int] = Field(
        default_factory=list,
        description='ID сообщений в viewport',
        max_length=100,
    )


class MarkChatMessagesVisibleResponse(BaseSchema):
    """Результат пометки ЛС прочитанными."""

    marked_ids: list[int] = Field(
        default_factory=list,
        description='Помеченные ID',
    )
    unread_count: int = Field(
        0,
        description='Оставшиеся непрочитанные ЛС',
    )
