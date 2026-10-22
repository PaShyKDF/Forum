"""API страницы «Связаться»."""

from fastapi import APIRouter

from forum.config import configuration
from forum.domain.schemas.contact import ContactPageResponse


router = APIRouter(
    tags=['contact'],
)

# Placeholder-фото для теста (абстрактный портрет)
_CONTACT_PHOTO_URL = (
    'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d'
    '?auto=format&fit=crop&w=640&q=80'
)

_CONTACT_BIO = (
    'Автор и куратор форума «Диагностика кармы. '
    'Взгляд изнутри». Помогаю участникам мягко '
    'разбираться в темах самопознания, отношений '
    'и личного опыта — через уважительный диалог '
    'и обмен наблюдениями. Если у вас есть вопрос '
    'по работе форума или предложение по развитию '
    'сообщества, напишите в удобный мессенджер.'
)


@router.get(
    '/contact',
    response_model=ContactPageResponse,
    summary='Страница «Связаться»',
)
async def get_contact_page() -> ContactPageResponse:
    """
    Отдаёт публичные данные страницы «Связаться».

    Returns:
        ContactPageResponse с bio, фото и ссылками
        на мессенджеры из configuration.contact.
    """
    contact = configuration.contact
    return ContactPageResponse(
        title='Связаться с автором',
        bio=_CONTACT_BIO,
        photo_url=_CONTACT_PHOTO_URL,
        telegram_url=contact.telegram_url.strip(),
        whatsapp_url=contact.whatsapp_url.strip(),
    )
