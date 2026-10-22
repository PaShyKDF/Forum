"""Схемы auth (OIDC-сессия)."""

from pydantic import Field

from forum.domain.schemas.base import BaseSchema
from forum.domain.schemas.users import UserResponse


class AuthSessionResponse(BaseSchema):
    """Текущая сессия после входа."""

    user: UserResponse
    message: str = Field(
        'Успешный вход',
        description='Сообщение',
    )
