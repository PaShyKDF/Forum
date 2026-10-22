from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema
from forum.domain.schemas.categories import (
    AuthorResponse,
    TopicSummaryResponse,
)
from forum.domain.schemas.posts import PaginatedPostsResponse
from forum.domain.schemas.sections import SectionBriefResponse


class CategoryBriefResponse(BaseSchema):
    """Краткие данные категории для хлебных крошек."""

    id: int = Field(..., description='ID категории')
    title: str = Field(..., description='Название категории')


class PostResponse(BaseSchema):
    """Сообщение в теме (legacy / детальный вид)."""

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
        description='ID сообщения, на которое ответили',
    )
    replies_count: int = Field(
        0,
        description='Число прямых ответов',
    )
    can_edit: bool = Field(
        False,
        description='Может ли текущий пользователь править',
    )
    author: AuthorResponse = Field(..., description='Автор')


class TopicDetailResponse(BaseSchema):
    """Страница темы: метаданные и первая страница корней."""

    id: int = Field(..., description='ID темы')
    title: str = Field(..., description='Название темы')
    description: str | None = Field(
        None,
        description='Описание темы',
    )
    is_pinned: bool = Field(..., description='Закреплена')
    is_closed: bool = Field(..., description='Закрыта')
    is_restricted: bool = Field(
        False,
        description='Скрытая тема',
    )
    can_manage: bool = Field(
        False,
        description='Админ может менять доступ',
    )
    can_edit_title: bool = Field(
        False,
        description=(
            'Автор может менять название в окне '
            'редактирования'
        ),
    )
    views_count: int = Field(..., description='Просмотры')
    section: SectionBriefResponse | None = Field(
        None,
        description='Раздел (хлебные крошки)',
    )
    category: CategoryBriefResponse = Field(
        ...,
        description='Категория темы',
    )
    posts: PaginatedPostsResponse = Field(
        ...,
        description='Корневые сообщения с пагинацией',
    )
    post_edit_window_hours: int = Field(
        ...,
        description='Окно редактирования сообщений в часах',
    )
    topic_edit_window_hours: int = Field(
        ...,
        description='Окно редактирования названия в часах',
    )


class CreateTopicRequest(BaseSchema):
    """Тело запроса на создание темы."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description='Название темы',
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description=(
            'Текст первого сообщения. Допустимы теги '
            'b, i, u, s, strike, del, strong, em, br'
        ),
    )
    description: str | None = Field(
        None,
        max_length=2000,
        description='Краткое описание темы',
    )
    is_restricted: bool = Field(
        False,
        description='Создать скрытую тему (только админ)',
    )
    allowed_user_uids: list[uuid.UUID] = Field(
        default_factory=list,
        description='Whitelist при создании скрытой темы',
    )


class VisibilityUpdateRequest(BaseSchema):
    """Скрыть или открыть категорию/тему."""

    is_restricted: bool = Field(
        ...,
        description='True — скрыть, False — открыть',
    )


class MembersUpdateRequest(BaseSchema):
    """Замена списка допущенных пользователей."""

    user_uids: list[uuid.UUID] = Field(
        default_factory=list,
        description='UID допущенных пользователей',
    )


class AccessMemberResponse(BaseSchema):
    """Пользователь в whitelist."""

    uid: uuid.UUID
    username: str
    display_name: str
    initials: str
    avatar_url: str | None = None


class CreateTopicResponse(BaseSchema):
    """Ответ после создания темы."""

    id: int = Field(..., description='ID новой темы')
    title: str = Field(..., description='Название темы')
    category_id: int = Field(..., description='ID категории')


class UpdateTopicTitleRequest(BaseSchema):
    """Тело запроса на смену названия темы."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description='Новое название темы',
    )


class UpdateTopicTitleResponse(BaseSchema):
    """Ответ после смены названия темы."""

    id: int = Field(..., description='ID темы')
    title: str = Field(..., description='Новое название')
    can_edit_title: bool = Field(
        ...,
        description='Можно ли ещё править название',
    )


__all__ = [
    'AccessMemberResponse',
    'CategoryBriefResponse',
    'CreateTopicRequest',
    'CreateTopicResponse',
    'MembersUpdateRequest',
    'PostResponse',
    'TopicDetailResponse',
    'TopicSummaryResponse',
    'UpdateTopicTitleRequest',
    'UpdateTopicTitleResponse',
    'VisibilityUpdateRequest',
]
