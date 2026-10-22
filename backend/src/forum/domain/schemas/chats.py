"""Схемы личных чатов и сообщений."""

from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema


class ChatPeerResponse(BaseSchema):
    """Собеседник в списке/шапке чата."""

    uid: uuid.UUID = Field(..., description='UID')
    display_name: str = Field(..., description='Ник')
    username: str = Field(..., description='Логин')
    initials: str = Field(..., description='Инициалы')
    avatar_url: str | None = Field(
        None,
        description='URL аватара',
    )
    has_avatar: bool = Field(
        False,
        description='Есть ли фото',
    )


class ChatLastMessageResponse(BaseSchema):
    """Превью последнего сообщения в списке чатов."""

    id: int = Field(..., description='ID сообщения')
    body: str = Field(..., description='Текст')
    kind: str = Field(..., description='Тип: text и др.')
    created_at: datetime = Field(..., description='Время')
    sender_id: uuid.UUID = Field(..., description='Автор')


class ChatItemResponse(BaseSchema):
    """Элемент списка диалогов."""

    id: int = Field(..., description='ID чата')
    peer: ChatPeerResponse = Field(
        ...,
        description='Собеседник',
    )
    last_message: ChatLastMessageResponse | None = Field(
        None,
        description='Последнее сообщение',
    )
    updated_at: datetime = Field(
        ...,
        description='Время активности чата',
    )
    unread_count: int = Field(
        0,
        description=(
            'Число непрочитанных входящих '
            'в этом диалоге'
        ),
        ge=0,
    )


class ChatMessageResponse(BaseSchema):
    """Сообщение в диалоге."""

    id: int = Field(..., description='ID')
    chat_id: int = Field(..., description='ID чата')
    sender_id: uuid.UUID = Field(..., description='Автор')
    body: str = Field(..., description='Текст')
    kind: str = Field(
        'text',
        description='Тип контента',
    )
    created_at: datetime = Field(..., description='Время')
    is_mine: bool = Field(
        ...,
        description='Отправлено текущим пользователем',
    )
    read_at: datetime | None = Field(
        None,
        description='Когда получатель увидел сообщение',
    )


class ChatMessagesPageResponse(BaseSchema):
    """Страница сообщений диалога."""

    chat_id: int = Field(..., description='ID чата')
    peer: ChatPeerResponse = Field(
        ...,
        description='Собеседник',
    )
    items: list[ChatMessageResponse] = Field(
        default_factory=list,
        description='Сообщения (старые → новые)',
    )
    has_more: bool = Field(
        False,
        description='Есть более старые сообщения',
    )


class CreateDirectMessageRequest(BaseSchema):
    """Тело запроса на отправку сообщения."""

    body: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description=(
            'Текст сообщения. Допустимы теги '
            'b, i, u, s, strike, del, strong, em, br'
        ),
    )
