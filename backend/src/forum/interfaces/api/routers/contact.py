"""API страницы «Связаться»."""

from fastapi import APIRouter

from forum.config import configuration
from forum.domain.schemas.contact import ContactPageResponse


router = APIRouter(
    tags=['contact'],
)

_CONTACT_PHOTO_URL = '/src/assets/icons/contact.jpg'
_CONTACT_AUTHOR_NAME = 'Клищенко Дмитрий Владимирович'

_CONTACT_BIO = (
    'Автор и куратор форума «Диагностика кармы. '
    'Взгляд изнутри». Помогаю участникам мягко '
    'разбираться в темах самопознания, отношений '
    'и личного опыта — через уважительный диалог '
    'и обмен наблюдениями. Если у вас есть предложение по '
    'развитию сообщества или необходимость в оперативной связи'
    ', напишите в удобный мессенджер.'
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
        author_name=_CONTACT_AUTHOR_NAME,
        bio=_CONTACT_BIO,
        photo_url=_CONTACT_PHOTO_URL,
        telegram_url=contact.telegram_url.strip(),
        whatsapp_url=contact.whatsapp_url.strip(),
    )
