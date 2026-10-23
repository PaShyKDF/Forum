"""Схемы страницы «Связаться»."""

from pydantic import Field

from forum.domain.schemas.base import BaseSchema


class ContactPageResponse(BaseSchema):
    """Данные публичной страницы контактов."""

    title: str = Field(..., description='Заголовок')
    author_name: str = Field(..., description='ФИО автора')
    bio: str = Field(..., description='Биография')
    photo_url: str = Field(..., description='URL фото')
    telegram_url: str = Field(
        ...,
        description='Ссылка на Telegram',
    )
    whatsapp_url: str = Field(
        ...,
        description='Ссылка на WhatsApp',
    )
