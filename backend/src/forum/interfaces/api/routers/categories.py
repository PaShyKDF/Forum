from fastapi import APIRouter, Depends, Query, Request, Response

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas import (
    CategoryDetailResponse,
    CategoryResponse,
    CreateTopicRequest,
    CreateTopicResponse,
    HomeResponse,
)
from forum.domain.schemas.topics import (
    AccessMemberResponse,
    MembersUpdateRequest,
    VisibilityUpdateRequest,
)
from forum.domain.schemas.users import UserResponse
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_dep import (
    get_current_user,
    get_forum_admin,
    get_optional_current_user,
)
from forum.service_layer.messagebus import MessageBus, get_message_bus
from forum.service_layer.visitor_cookies import (
    read_anon_id,
    set_anon_cookie,
)


router = APIRouter(
    prefix='/categories',
    tags=['categories'],
)

home_router = APIRouter(
    tags=['home'],
)


@home_router.get(
    '/home',
    response_model=HomeResponse,
    summary='Контент главной страницы',
    description=(
        'Специальные и обычные разделы форума. '
        'Сортировка по position ASC.'
    ),
)
async def get_home(
    request: Request,
    response: Response,
    message_bus: MessageBus = Depends(get_message_bus),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
) -> HomeResponse:
    """
    Отдаёт контент главной и учитывает визит гостя.

    При анонимном визите может выставить cookie anon_id.

    Args:
        request: HTTP-запрос (User-Agent, cookies).
        response: ответ для Set-Cookie anon_id.
        message_bus: Depends MessageBus.
        current_user: текущий пользователь или None.

    Returns:
        HomeResponse со специальными и обычными разделами.
    """
    track_result = await message_bus.handle(
        commands.TrackGuestVisitCommand(
            anon_id=read_anon_id(request),
            user_agent=request.headers.get('user-agent'),
            is_authenticated=current_user is not None,
        ),
    )
    if track_result.set_cookie and track_result.anon_id:
        set_anon_cookie(response, track_result.anon_id)
    return await message_bus.handle(
        commands.GetHomeCommand(
            current_user_uid=(
                current_user.uid if current_user else None
            ),
            is_admin=bool(
                current_user and current_user.is_admin,
            ),
        ),
    )


@router.get(
    '',
    response_model=list[CategoryResponse],
    summary='Список категорий',
    description=(
        'Фильтр section_id и сортировка по position '
        'от меньшей к большей.'
    ),
)
async def get_categories(
    section_id: int | None = Query(
        None,
        description='ID раздела для фильтрации',
    ),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[CategoryResponse]:
    """
    Возвращает список категорий с учётом доступа.

    Args:
        section_id: ID раздела для фильтра или None.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        Список CategoryResponse (position ASC).
    """
    command = commands.GetCategoriesCommand(
        section_id=section_id,
        current_user_uid=(
            current_user.uid if current_user else None
        ),
        is_admin=bool(
            current_user and current_user.is_admin,
        ),
    )
    return await message_bus.handle(command)


@router.get(
    '/{category_id}',
    response_model=CategoryDetailResponse,
    summary='Категория со списком тем',
    description=(
        'Страница категории: темы по position ASC '
        'со счётчиками и последним сообщением.'
    ),
)
async def get_category_by_id(
    category_id: int,
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> CategoryDetailResponse:
    """
    Возвращает категорию и список тем в ней.

    Args:
        category_id: ID категории.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        CategoryDetailResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.GetCategoryByIdCommand(
        category_id=category_id,
        current_user_uid=(
            current_user.uid if current_user else None
        ),
        is_admin=bool(
            current_user and current_user.is_admin,
        ),
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/{category_id}/topics',
    response_model=CreateTopicResponse,
    summary='Создать тему в категории',
    description=(
        'Создаёт тему и первое сообщение. '
        'Требует авторизации.'
    ),
    status_code=201,
)
async def create_topic(
    category_id: int,
    payload: CreateTopicRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> CreateTopicResponse:
    """
    Создаёт тему и первое сообщение в категории.

    Args:
        category_id: ID категории.
        payload: title, body и опции доступа.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        CreateTopicResponse созданной темы.

    Raises:
        HTTPException: при доменной ошибке прав/уникальности.
    """
    command = commands.CreateTopicCommand(
        category_id=category_id,
        author_id=current_user.uid,
        title=payload.title,
        body=payload.body,
        description=payload.description,
        is_restricted=payload.is_restricted,
        allowed_user_uids=payload.allowed_user_uids,
        is_admin=current_user.is_admin,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{category_id}/members',
    response_model=list[AccessMemberResponse],
    summary='Допущенные к категории',
)
async def get_category_members(
    category_id: int,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[AccessMemberResponse]:
    """
    Список пользователей с допуском к категории.

    Args:
        category_id: ID категории.
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        Список AccessMemberResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    try:
        return await message_bus.handle(
            commands.GetCategoryMembersCommand(
                category_id=category_id,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)


@router.put(
    '/{category_id}/members',
    response_model=list[AccessMemberResponse],
    summary='Обновить допуск к категории',
)
async def set_category_members(
    category_id: int,
    payload: MembersUpdateRequest,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[AccessMemberResponse]:
    """
    Задаёт whitelist допущенных к категории.

    Args:
        category_id: ID категории.
        payload: список user_uids.
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        Обновлённый список AccessMemberResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    try:
        return await message_bus.handle(
            commands.SetCategoryMembersCommand(
                category_id=category_id,
                user_uids=payload.user_uids,
                actor_uid=current_user.uid,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)


@router.patch(
    '/{category_id}/visibility',
    summary='Скрыть или открыть категорию',
)
async def set_category_visibility(
    category_id: int,
    payload: VisibilityUpdateRequest,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> dict:
    """
    Делает категорию скрытой или открытой для всех.

    Args:
        category_id: ID категории.
        payload: флаг is_restricted.
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        Словарь с результатом команды.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    try:
        return await message_bus.handle(
            commands.SetCategoryVisibilityCommand(
                category_id=category_id,
                is_restricted=payload.is_restricted,
                actor_uid=current_user.uid,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)
