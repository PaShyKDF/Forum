"""API уведомлений о ответах и цитатах."""

from fastapi import APIRouter, Depends, Query

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas.base import SuccessResponse
from forum.domain.schemas.notifications import (
    TopicNotificationsListResponse,
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
    prefix='/notifications',
    tags=['notifications'],
)


@router.get(
    '',
    response_model=TopicNotificationsListResponse,
    summary='Мои непрочитанные уведомления',
)
async def get_my_notifications(
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> TopicNotificationsListResponse:
    """
    Возвращает непрочитанные уведомления пользователя.

    Args:
        limit: максимум записей (1–100).
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        TopicNotificationsListResponse.

    Raises:
        HTTPException: при доменной ошибке.
    """
    command = commands.GetMyNotificationsCommand(
        current_user_uid=current_user.uid,
        limit=limit,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/{notification_id}/read',
    response_model=SuccessResponse,
    summary='Отметить уведомление прочитанным',
)
async def mark_notification_read(
    notification_id: int,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SuccessResponse:
    """
    Отмечает одно уведомление прочитанным.

    Args:
        notification_id: ID уведомления.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        SuccessResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.MarkNotificationReadCommand(
        notification_id=notification_id,
        current_user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.delete(
    '/{notification_id}',
    response_model=SuccessResponse,
    summary='Удалить уведомление из списка',
)
async def dismiss_notification(
    notification_id: int,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SuccessResponse:
    """
    Удаляет уведомление из списка пользователя.

    Args:
        notification_id: ID уведомления.
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        SuccessResponse.

    Raises:
        HTTPException: при доменной ошибке доступа/наличия.
    """
    command = commands.DismissNotificationCommand(
        notification_id=notification_id,
        current_user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/clear',
    response_model=SuccessResponse,
    summary='Очистить все уведомления',
)
async def clear_notifications(
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SuccessResponse:
    """
    Очищает все уведомления текущего пользователя.

    Args:
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        SuccessResponse.

    Raises:
        HTTPException: при доменной ошибке.
    """
    command = commands.ClearNotificationsCommand(
        current_user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
