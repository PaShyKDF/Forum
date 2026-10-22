"""API разделов форума."""

from fastapi import APIRouter, Depends, Query

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas.categories import (
    CreateCategoryRequest,
    CreateCategoryResponse,
    SectionDetailResponse,
)
from forum.domain.schemas.sections import SectionResponse
from forum.domain.schemas.users import UserResponse
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_dep import (
    get_forum_admin,
    get_optional_current_user,
)
from forum.service_layer.messagebus import MessageBus, get_message_bus


router = APIRouter(
    prefix='/sections',
    tags=['sections'],
)


@router.get(
    '',
    response_model=list[SectionResponse],
    summary='Список разделов',
    description=(
        'Фильтр is_topic и сортировка по position '
        'от меньшей к большей.'
    ),
)
async def get_sections(
    is_topic: bool | None = Query(
        None,
        description=(
            'True — специальные разделы, '
            'False — обычные'
        ),
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[SectionResponse]:
    """
    Возвращает список разделов форума.

    Args:
        is_topic: True — спецразделы, False — обычные,
            None — все.
        message_bus: Depends MessageBus.

    Returns:
        Список SectionResponse (position ASC).
    """
    command = commands.GetSectionsCommand(is_topic=is_topic)
    return await message_bus.handle(command)


@router.get(
    '/{section_id}',
    response_model=SectionDetailResponse,
    summary='Раздел со списком категорий',
    description='Страница раздела: категории по position ASC.',
)
async def get_section_by_id(
    section_id: int,
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SectionDetailResponse:
    """
    Возвращает раздел со списком категорий.

    Args:
        section_id: ID раздела.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        SectionDetailResponse.
    """
    command = commands.GetSectionByIdCommand(
        section_id=section_id,
        current_user_uid=(
            current_user.uid if current_user else None
        ),
        is_admin=bool(
            current_user and current_user.is_admin,
        ),
    )
    return await message_bus.handle(command)


@router.post(
    '/{section_id}/categories',
    response_model=CreateCategoryResponse,
    summary='Создать категорию в разделе',
    description=(
        'Только администратор. Можно сразу сделать '
        'скрытой и задать whitelist.'
    ),
    status_code=201,
)
async def create_category(
    section_id: int,
    payload: CreateCategoryRequest,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> CreateCategoryResponse:
    """
    Создаёт категорию в разделе (только админ).

    Args:
        section_id: ID раздела.
        payload: title, description и опции доступа.
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        CreateCategoryResponse созданной категории.

    Raises:
        HTTPException: при доменной ошибке прав/уникальности.
    """
    command = commands.CreateCategoryCommand(
        section_id=section_id,
        title=payload.title,
        description=payload.description,
        is_restricted=payload.is_restricted,
        allowed_user_uids=payload.allowed_user_uids,
        is_admin=True,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
