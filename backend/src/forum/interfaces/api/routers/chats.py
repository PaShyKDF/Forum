"""API личных чатов 1-на-1."""

import uuid

from fastapi import APIRouter, Depends, Query

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas.chats import (
    ChatItemResponse,
    ChatMessageResponse,
    ChatMessagesPageResponse,
    CreateDirectMessageRequest,
)
from forum.domain.schemas.notifications import (
    MarkChatMessagesVisibleRequest,
    MarkChatMessagesVisibleResponse,
    UnreadCountResponse,
)
from forum.domain.schemas.users import UserResponse
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_dep import get_current_user
from forum.service_layer.messagebus import (
    MessageBus,
    get_message_bus,
)


router = APIRouter(
    prefix='/chats',
    tags=['chats'],
)


@router.get(
    '',
    response_model=list[ChatItemResponse],
    summary='Мои диалоги',
)
async def get_my_chats(
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[ChatItemResponse]:
    """
    Возвращает список диалогов текущего пользователя.

    Args:
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        Список ChatItemResponse.

    Raises:
        HTTPException: при доменной ошибке.
    """
    command = commands.GetMyChatsCommand(
        current_user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/unread-count',
    response_model=UnreadCountResponse,
    summary='Число непрочитанных личных сообщений',
)
async def get_unread_chat_count(
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UnreadCountResponse:
    """
    Считает непрочитанные личные сообщения.

    Args:
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UnreadCountResponse.

    Raises:
        HTTPException: при доменной ошибке.
    """
    command = commands.GetUnreadChatCountCommand(
        current_user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/messages/mark-visible',
    response_model=MarkChatMessagesVisibleResponse,
    summary='Пометить видимые ЛС прочитанными',
)
async def mark_chat_messages_visible(
    payload: MarkChatMessagesVisibleRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> MarkChatMessagesVisibleResponse:
    """
    Помечает указанные ЛС прочитанными (видимыми).

    Args:
        payload: список message_ids.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        MarkChatMessagesVisibleResponse.

    Raises:
        HTTPException: при доменной ошибке доступа.
    """
    command = commands.MarkChatMessagesVisibleCommand(
        current_user_uid=current_user.uid,
        message_ids=payload.message_ids,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/direct/{user_uid}',
    response_model=ChatItemResponse,
    summary='Открыть или создать диалог',
    status_code=200,
)
async def get_or_create_direct_chat(
    user_uid: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ChatItemResponse:
    """
    Открывает или создаёт диалог 1-на-1 с пользователем.

    Args:
        user_uid: UUID собеседника.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        ChatItemResponse диалога.

    Raises:
        HTTPException: 422 при чате с собой; иначе доменные.
    """
    command = commands.GetOrCreateDirectChatCommand(
        current_user_uid=current_user.uid,
        other_user_uid=user_uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{chat_id}/messages',
    response_model=ChatMessagesPageResponse,
    summary='Сообщения диалога',
)
async def get_chat_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: int | None = Query(
        None,
        description='Загрузить сообщения старше этого id',
    ),
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ChatMessagesPageResponse:
    """
    Возвращает страницу сообщений диалога.

    Args:
        chat_id: ID чата.
        limit: максимум сообщений за запрос.
        before_id: загрузить старше этого id или None.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        ChatMessagesPageResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.GetChatMessagesCommand(
        chat_id=chat_id,
        current_user_uid=current_user.uid,
        limit=limit,
        before_id=before_id,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/{chat_id}/messages',
    response_model=ChatMessageResponse,
    summary='Отправить сообщение',
    status_code=201,
)
async def send_chat_message(
    chat_id: int,
    payload: CreateDirectMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ChatMessageResponse:
    """
    Отправляет личное сообщение в диалог.

    Args:
        chat_id: ID чата.
        payload: текст сообщения.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        ChatMessageResponse созданного сообщения.

    Raises:
        HTTPException: при доменной ошибке доступа/лимита.
    """
    command = commands.SendDirectMessageCommand(
        chat_id=chat_id,
        current_user_uid=current_user.uid,
        body=payload.body,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
