from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema
from forum.domain.schemas.sections import SectionBriefResponse


class LastPostResponse(BaseSchema):
    """Превью последнего сообщения в теме."""

    title: str = Field(..., description='Заголовок темы')
    author: str = Field(..., description='Имя автора')
    author_uid: uuid.UUID | None = Field(
        None,
        description='UID автора для ссылки на профиль',
    )
    created_at: datetime = Field(
        ...,
        description='Время создания сообщения',
    )
    topic_id: int | None = Field(
        None,
        description='ID темы последнего сообщения',
    )


class AuthorResponse(BaseSchema):
    """Краткие данные автора сообщения."""

    uid: uuid.UUID = Field(..., description='UID пользователя')
    display_name: str = Field(..., description='Отображаемое имя')
    initials: str = Field(..., description='Инициалы для аватара')
    avatar_url: str | None = Field(
        None,
        description='URL аватара',
    )


class TopicSummaryResponse(BaseSchema):
    """Тема в списках (категория, активные)."""

    id: int = Field(..., description='ID темы')
    title: str = Field(..., description='Название темы')
    description: str | None = Field(
        None,
        description='Описание темы',
    )
    category_id: int = Field(..., description='ID категории')
    position: int = Field(..., description='Порядок сортировки')
    is_topic: bool = Field(
        ...,
        description='Тема для специальных разделов',
    )
    is_pinned: bool = Field(
        ...,
        description='Закреплена в категории',
    )
    is_restricted: bool = Field(
        False,
        description='Скрытая тема (whitelist)',
    )
    can_manage: bool = Field(
        False,
        description='Админ может менять доступ',
    )
    posts_count: int = Field(
        ...,
        description='Число сообщений',
    )
    last_post: LastPostResponse | None = Field(
        None,
        description='Последнее сообщение',
    )


class CategoryResponse(BaseSchema):
    """Категория со счётчиками для списков."""

    id: int = Field(..., description='ID категории')
    title: str = Field(..., description='Название')
    description: str | None = Field(
        None,
        description='Описание',
    )
    position: int = Field(..., description='Порядок сортировки')
    section_id: int | None = Field(
        None,
        description='ID раздела',
    )
    is_restricted: bool = Field(
        False,
        description='Скрытая категория (whitelist)',
    )
    can_manage: bool = Field(
        False,
        description='Админ может менять доступ',
    )
    topics_count: int = Field(
        0,
        description='Число тем',
    )
    posts_count: int = Field(
        0,
        description='Число сообщений',
    )
    last_post: LastPostResponse | None = Field(
        None,
        description='Последнее сообщение',
    )


class CategoryDetailResponse(BaseSchema):
    """Страница категории со списком тем."""

    id: int = Field(..., description='ID категории')
    title: str = Field(..., description='Название')
    description: str | None = Field(
        None,
        description='Описание',
    )
    position: int = Field(..., description='Порядок сортировки')
    is_restricted: bool = Field(
        False,
        description='Скрытая категория',
    )
    can_manage: bool = Field(
        False,
        description='Админ может менять доступ',
    )
    section: SectionBriefResponse | None = Field(
        None,
        description='Раздел категории',
    )
    topics: list[TopicSummaryResponse] = Field(
        default_factory=list,
        description='Темы категории',
    )


class SectionDetailResponse(BaseSchema):
    """Страница раздела со списком категорий."""

    id: int = Field(..., description='ID раздела')
    title: str = Field(..., description='Название')
    position: int = Field(..., description='Порядок сортировки')
    is_topic: bool = Field(
        ...,
        description='Специальный раздел',
    )
    categories: list[CategoryResponse] = Field(
        default_factory=list,
        description='Категории раздела',
    )


class HomeResponse(BaseSchema):
    """
    Контент главной: спец. и обычные разделы
    с вложенными категориями и статистикой.
    """

    special_sections: list[SectionDetailResponse] = Field(
        default_factory=list,
        description='Специальные разделы',
    )
    sections: list[SectionDetailResponse] = Field(
        default_factory=list,
        description='Обычные разделы',
    )
    community_members_count: int = Field(
        0,
        ge=0,
        description='Число участников сообщества',
    )
    today_active_members_count: int = Field(
        0,
        ge=0,
        description='Активны сегодня (с 00:00 МСК)',
    )


class CreateCategoryRequest(BaseSchema):
    """Тело запроса на создание категории."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description='Название категории',
    )
    description: str | None = Field(
        None,
        max_length=2000,
        description=(
            'Описание. Допустимы теги '
            'b, i, u, s, strike, del, strong, em, br'
        ),
    )
    is_restricted: bool = Field(
        False,
        description='Создать скрытую категорию',
    )
    allowed_user_uids: list[uuid.UUID] = Field(
        default_factory=list,
        description=(
            'Whitelist при создании скрытой категории'
        ),
    )


class CreateCategoryResponse(BaseSchema):
    """Ответ после создания категории."""

    id: int = Field(..., description='ID новой категории')
    title: str = Field(..., description='Название')
    section_id: int = Field(..., description='ID раздела')
