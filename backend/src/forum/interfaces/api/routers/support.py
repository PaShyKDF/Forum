"""API технической поддержки."""

from fastapi import APIRouter, Depends, Request

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas.support import (
    CreateSupportTicketRequest,
    SupportTicketResponse,
)
from forum.domain.schemas.users import UserResponse
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_dep import (
    get_optional_current_user,
)
from forum.service_layer.client_ip import resolve_client_ip
from forum.service_layer.messagebus import (
    MessageBus,
    get_message_bus,
)


router = APIRouter(
    prefix='/support',
    tags=['support'],
)


@router.post(
    '/tickets',
    response_model=SupportTicketResponse,
    summary='Отправить обращение в техподдержку',
    status_code=201,
)
async def create_support_ticket(
    payload: CreateSupportTicketRequest,
    request: Request,
    current_user: UserResponse | None = Depends(
        get_optional_current_user,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> SupportTicketResponse:
    """
    Создаёт обращение в техническую поддержку.

    Доступно гостям и авторизованным; IP берётся из
    заголовков прокси.

    Args:
        payload: subject, body и email.
        request: HTTP-запрос (IP клиента).
        current_user: текущий пользователь или None.
        message_bus: Depends MessageBus.

    Returns:
        SupportTicketResponse созданного тикета.

    Raises:
        HTTPException: при доменной ошибке (лимит и т.п.).
    """
    command = commands.CreateSupportTicketCommand(
        subject=payload.subject,
        body=payload.body,
        email=payload.email,
        user_uid=current_user.uid if current_user else None,
        client_ip=await resolve_client_ip(request),
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
