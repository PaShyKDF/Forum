"""Схемы сообщений и пагинации обсуждений."""

from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema
from forum.domain.schemas.categories import AuthorResponse


class CreatePostRequest(BaseSchema):
    """Тело запроса на создание сообщения."""

    body: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description=(
            'Текст сообщения. Допустимы теги '
            'b, i, u, s, strike, del, strong, em, br'
        ),
    )
    quoted_post_id: int | None = Field(
        None,
        description='ID цитируемого сообщения',
    )


class UpdatePostRequest(BaseSchema):
    """Тело запроса на редактирование сообщения."""

    body: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description=(
            'Новый текст. Допустимы теги '
            'b, i, u, s, strike, del, strong, em, br'
        ),
    )
    quoted_post_id: int | None = Field(
        None,
        description='ID цитируемого сообщения',
    )


class QuotedPostResponse(BaseSchema):
    """Краткие данные цитируемого сообщения."""

    id: int = Field(..., description='ID цитаты')
    body_snippet: str = Field(
        ...,
        description='Краткий текст цитаты',
    )
    author_display_name: str = Field(
        ...,
        description='Имя автора цитаты',
    )
    author_uid: uuid.UUID | None = Field(
        None,
        description='UID автора цитаты',
    )
    jump_target: str = Field(
        ...,
        description='Якорь для перехода к цитате',
    )


class PostItemResponse(BaseSchema):
    """Сообщение в списке корней или ответов."""

    id: int = Field(..., description='ID сообщения')
    body: str = Field(..., description='Текст сообщения')
    created_at: datetime = Field(
        ...,
        description='Время создания',
    )
    updated_at: datetime = Field(
        ...,
        description='Время обновления',
    )
    is_topic_starter: bool = Field(
        ...,
        description='Стартовое сообщение темы',
    )
    reply_to_post_id: int | None = Field(
        None,
        description='ID корневого сообщения-родителя',
    )
    quoted_post: QuotedPostResponse | None = Field(
        None,
        description='Цитируемое сообщение',
    )
    replies_count: int = Field(
        0,
        description='Число прямых ответов',
    )
    can_edit: bool = Field(
        False,
        description='Может ли текущий пользователь править',
    )
    author: AuthorResponse = Field(
        ...,
        description='Автор',
    )


class PaginatedPostsResponse(BaseSchema):
    """Страница сообщений (корни или ответы)."""

    items: list[PostItemResponse] = Field(
        default_factory=list,
        description='Сообщения страницы',
    )
    page: int = Field(..., description='Текущая страница')
    page_size: int = Field(..., description='Размер страницы')
    total: int = Field(..., description='Всего элементов')
    total_pages: int = Field(
        ...,
        description='Всего страниц',
    )


__all__ = [
    'CreatePostRequest',
    'UpdatePostRequest',
    'QuotedPostResponse',
    'PostItemResponse',
    'PaginatedPostsResponse',
]
