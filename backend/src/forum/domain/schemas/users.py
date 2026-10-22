from datetime import datetime
import uuid

from pydantic import Field

from forum.domain.schemas.base import BaseSchema


class UserCreate(BaseSchema):
    """Данные для создания пользователя из Keycloak."""

    uid: uuid.UUID = Field(..., description='UID из Keycloak (sub)')
    username: str = Field(..., description='Логин')
    email: str | None = Field(None, description='Email')
    email_verified: bool = Field(
        False,
        description='Email подтверждён',
    )
    display_name: str = Field(..., description='Отображаемое имя')
    initials: str = Field(..., description='Инициалы для аватара')
    avatar_url: str | None = Field(
        None,
        description='URL аватара',
    )


class UserResponse(BaseSchema):
    """Публичные данные пользователя."""

    uid: uuid.UUID = Field(..., description='UID пользователя')
    username: str = Field(..., description='Логин')
    email: str | None = Field(None, description='Email')
    email_verified: bool = Field(
        ...,
        description='Email подтверждён',
    )
    display_name: str = Field(..., description='Отображаемое имя')
    initials: str = Field(..., description='Инициалы для аватара')
    avatar_url: str | None = Field(
        None,
        description='URL аватара (endpoint или внешний)',
    )
    has_avatar: bool = Field(
        False,
        description='Есть ли загруженное фото в БД',
    )
    is_admin: bool = Field(
        False,
        description='Роль администратора форума',
    )


class UserProfileResponse(UserResponse):
    """Профиль пользователя со статистикой."""

    posts_count: int = Field(
        ...,
        ge=0,
        description='Число активных сообщений',
    )


class PublicUserProfileResponse(BaseSchema):
    """Публичный профиль другого пользователя."""

    uid: uuid.UUID = Field(..., description='UID пользователя')
    username: str = Field(..., description='Логин')
    display_name: str = Field(
        ...,
        description='Отображаемое имя (ник)',
    )
    initials: str = Field(..., description='Инициалы')
    avatar_url: str | None = Field(
        None,
        description='URL аватара',
    )
    has_avatar: bool = Field(
        False,
        description='Есть ли загруженное фото',
    )
    is_active: bool = Field(
        ...,
        description='Активен ли аккаунт',
    )
    created_at: datetime = Field(
        ...,
        description='Дата регистрации',
    )
    last_seen_at: datetime | None = Field(
        None,
        description='Дата последнего посещения',
    )
    posts_count: int = Field(
        ...,
        ge=0,
        description='Число активных сообщений',
    )
    topics_count: int = Field(
        ...,
        ge=0,
        description='Число созданных тем',
    )


class UpdateUserProfileRequest(BaseSchema):
    """Обновление полей профиля."""

    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=120,
        description='Отображаемое имя (никнейм)',
    )


class ChangePasswordUrlResponse(BaseSchema):
    """Ссылка на смену пароля в Keycloak."""

    url: str = Field(..., description='URL OIDC с kc_action')
