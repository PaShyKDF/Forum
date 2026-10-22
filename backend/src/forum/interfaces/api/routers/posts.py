"""API сообщений: ответы и редактирование."""

from fastapi import APIRouter, Depends, Query

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas import (
    CreatePostRequest,
    PaginatedPostsResponse,
    PostItemResponse,
    UpdatePostRequest,
)
from forum.domain.schemas.users import UserResponse
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_dep import (
    get_current_user,
    get_optional_current_user,
)
from forum.service_layer.messagebus import MessageBus, get_message_bus


router = APIRouter(
    prefix='/posts',
    tags=['posts'],
)


@router.get(
    '/{post_id}/replies',
    response_model=PaginatedPostsResponse,
    summary='Ответы на сообщение',
    description=(
        'Прямые ответы на сообщение с пагинацией '
        '(новые сверху).'
    ),
)
async def get_post_replies(
    post_id: int,
    page: int = Query(1, ge=1, description='Страница'),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description='Размер страницы ответов',
    ),
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> PaginatedPostsResponse:
    """
    Возвращает страницу прямых ответов на сообщение.

    Args:
        post_id: ID родительского сообщения.
        page: номер страницы (с 1).
        page_size: размер страницы или None.
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        PaginatedPostsResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.GetPostRepliesCommand(
        post_id=post_id,
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
    '/{post_id}/replies',
    response_model=PostItemResponse,
    summary='Ответить на сообщение',
    description='Создаёт ответ на указанное сообщение.',
    status_code=201,
)
async def create_reply(
    post_id: int,
    payload: CreatePostRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> PostItemResponse:
    """
    Создаёт ответ на указанное сообщение.

    Args:
        post_id: ID родительского сообщения.
        payload: текст и опциональная цитата.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        PostItemResponse созданного ответа.

    Raises:
        HTTPException: при доменной ошибке (вложенность и т.п.).
    """
    command = commands.CreateReplyCommand(
        parent_post_id=post_id,
        author_id=current_user.uid,
        body=payload.body,
        quoted_post_id=payload.quoted_post_id,
        is_admin=current_user.is_admin,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.patch(
    '/{post_id}',
    response_model=PostItemResponse,
    summary='Редактировать сообщение',
    description=(
        'Автор может править сообщение в пределах '
        'окна из FORUM_POST_EDIT_WINDOW_HOURS.'
    ),
)
async def update_post(
    post_id: int,
    payload: UpdatePostRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> PostItemResponse:
    """
    Редактирует сообщение автором в окне правки.

    Args:
        post_id: ID сообщения.
        payload: новый текст и цитата.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        PostItemResponse после обновления.

    Raises:
        HTTPException: при доменной ошибке прав/окна правки.
    """
    command = commands.UpdatePostCommand(
        post_id=post_id,
        author_id=current_user.uid,
        body=payload.body,
        quoted_post_id=payload.quoted_post_id,
        is_admin=current_user.is_admin,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
