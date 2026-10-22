from fastapi import APIRouter, Depends, HTTPException, Query

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas import (
    CreatePostRequest,
    PaginatedPostsResponse,
    PostItemResponse,
    TopicDetailResponse,
    TopicSummaryResponse,
)
from forum.domain.schemas.topics import (
    AccessMemberResponse,
    MembersUpdateRequest,
    UpdateTopicTitleRequest,
    UpdateTopicTitleResponse,
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


router = APIRouter(
    prefix='/topics',
    tags=['topics'],
)


@router.get(
    '',
    response_model=list[TopicSummaryResponse],
    summary='Список тем',
    description=(
        'Фильтры category_id, is_topic и filter '
        '(active / participated).'
    ),
)
async def get_topics(
    category_id: int | None = Query(
        None,
        description='ID категории',
    ),
    is_topic: bool | None = Query(
        None,
        description='True — темы специальных разделов',
    ),
    filter_name: str | None = Query(
        None,
        alias='filter',
        description='active | participated',
    ),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[TopicSummaryResponse]:
    """
    Возвращает список тем с опциональными фильтрами.

    Args:
        category_id: ID категории или None.
        is_topic: фильтр специальных разделов или None.
        filter_name: active | participated или None.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        Список TopicSummaryResponse.

    Raises:
        HTTPException: 401 при filter=participated без входа.
    """
    filter_by = None
    if filter_name in {'active', 'participated'}:
        filter_by = filter_name
    user_uid = current_user.uid if current_user else None
    if filter_by == 'participated' and user_uid is None:
        raise HTTPException(
            status_code=401,
            detail='Не авторизован',
        )
    command = commands.GetTopicsCommand(
        category_id=category_id,
        is_topic=is_topic,
        filter_by=filter_by,
        current_user_uid=user_uid,
        is_admin=bool(
            current_user and current_user.is_admin,
        ),
    )
    return await message_bus.handle(command)


@router.get(
    '/{topic_id}',
    response_model=TopicDetailResponse,
    summary='Тема со сообщениями',
    description=(
        'Метаданные темы и страница корневых сообщений '
        '(новые сверху).'
    ),
)
async def get_topic_by_id(
    topic_id: int,
    page: int = Query(1, ge=1, description='Страница'),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description='Размер страницы корней',
    ),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> TopicDetailResponse:
    """
    Возвращает тему и страницу корневых сообщений.

    Args:
        topic_id: ID темы.
        page: номер страницы (с 1).
        page_size: размер страницы корней или None.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        TopicDetailResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.GetTopicByIdCommand(
        topic_id=topic_id,
        page=page,
        page_size=page_size,
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


@router.patch(
    '/{topic_id}',
    response_model=UpdateTopicTitleResponse,
    summary='Изменить название темы',
    description=(
        'Автор может править название в пределах окна '
        'из FORUM_TOPIC_EDIT_WINDOW_HOURS.'
    ),
)
async def update_topic_title(
    topic_id: int,
    payload: UpdateTopicTitleRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UpdateTopicTitleResponse:
    """
    Меняет название темы автором в окне редактирования.

    Args:
        topic_id: ID темы.
        payload: новое название.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UpdateTopicTitleResponse.

    Raises:
        HTTPException: при доменной ошибке прав/окна правки.
    """
    command = commands.UpdateTopicTitleCommand(
        topic_id=topic_id,
        author_id=current_user.uid,
        title=payload.title,
        is_admin=current_user.is_admin,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{topic_id}/posts',
    response_model=PaginatedPostsResponse,
    summary='Корневые сообщения темы',
    description='Пагинация корневых сообщений (новые сверху).',
)
async def get_topic_posts(
    topic_id: int,
    page: int = Query(1, ge=1, description='Страница'),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description='Размер страницы',
    ),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> PaginatedPostsResponse:
    """
    Возвращает страницу корневых сообщений темы.

    Args:
        topic_id: ID темы.
        page: номер страницы (с 1).
        page_size: размер страницы или None.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        PaginatedPostsResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.GetTopicPostsCommand(
        topic_id=topic_id,
        page=page,
        page_size=page_size,
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
    '/{topic_id}/posts',
    response_model=PostItemResponse,
    summary='Ответить в теме',
    description='Создаёт корневое сообщение в теме.',
    status_code=201,
)
async def create_topic_post(
    topic_id: int,
    payload: CreatePostRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> PostItemResponse:
    """
    Создаёт корневое сообщение в теме.

    Args:
        topic_id: ID темы.
        payload: текст и опциональная цитата.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        PostItemResponse созданного сообщения.

    Raises:
        HTTPException: при доменной ошибке (закрыта тема и т.п.).
    """
    command = commands.CreateTopicPostCommand(
        topic_id=topic_id,
        author_id=current_user.uid,
        body=payload.body,
        quoted_post_id=payload.quoted_post_id,
        is_admin=current_user.is_admin,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{topic_id}/members',
    response_model=list[AccessMemberResponse],
    summary='Допущенные к теме',
)
async def get_topic_members(
    topic_id: int,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[AccessMemberResponse]:
    """
    Список пользователей с допуском к скрытой теме.

    Args:
        topic_id: ID темы.
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        Список AccessMemberResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    try:
        return await message_bus.handle(
            commands.GetTopicMembersCommand(
                topic_id=topic_id,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)


@router.put(
    '/{topic_id}/members',
    response_model=list[AccessMemberResponse],
    summary='Обновить допуск к теме',
)
async def set_topic_members(
    topic_id: int,
    payload: MembersUpdateRequest,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[AccessMemberResponse]:
    """
    Задаёт whitelist допущенных к теме пользователей.

    Args:
        topic_id: ID темы.
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
            commands.SetTopicMembersCommand(
                topic_id=topic_id,
                user_uids=payload.user_uids,
                actor_uid=current_user.uid,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)


@router.patch(
    '/{topic_id}/visibility',
    summary='Скрыть или открыть тему',
)
async def set_topic_visibility(
    topic_id: int,
    payload: VisibilityUpdateRequest,
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> dict:
    """
    Делает тему скрытой или открытой для всех.

    Args:
        topic_id: ID темы.
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
            commands.SetTopicVisibilityCommand(
                topic_id=topic_id,
                is_restricted=payload.is_restricted,
                actor_uid=current_user.uid,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)
