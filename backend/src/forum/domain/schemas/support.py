"""Схемы обращений в техподдержку."""

from datetime import datetime

from pydantic import Field, field_validator

from forum.domain.schemas.base import BaseSchema


class CreateSupportTicketRequest(BaseSchema):
    """Запрос на создание обращения."""

    subject: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description='Тема обращения',
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description='Текст обращения',
    )
    email: str | None = Field(
        None,
        max_length=320,
        description='Email (для гостя обязателен)',
    )

    @field_validator('subject', 'body')
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('Поле не может быть пустым')
        return cleaned

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


class SupportTicketResponse(BaseSchema):
    """Ответ после создания обращения."""

    id: int = Field(..., description='ID обращения')
    status: str = Field(..., description='Статус')
    created_at: datetime = Field(..., description='Создано')
    message: str = Field(
        ...,
        description='Текст подтверждения',
    )
