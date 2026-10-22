"""Handlers обращений в техподдержку."""

import re
import uuid

from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from forum.domain.models import SupportTicket
from forum.domain.schemas.support import SupportTicketResponse
from forum.service_layer import unit_of_work
from forum.service_layer.handlers.spam_guard import (
    check_support_ticket_daily_limit,
)


_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$',
)


def _require_non_empty(value: str, field_name: str) -> str:
    """
    Обрезает пробелы и запрещает пустое значение.

    Args:
        value: Исходная строка поля.
        field_name: Имя поля для текста ошибки.

    Returns:
        Непустая строка после strip.

    Raises:
        DomainError: Если значение пустое.
    """
    cleaned = value.strip()
    if not cleaned:
        raise DomainError(
            f'{field_name} не может быть пустым',
            'EMPTY_FIELD',
        )
    return cleaned


def _validate_guest_email(email: str | None) -> str:
    """
    Проверяет email гостя для обратной связи.

    Args:
        email: Адрес из формы или None.

    Returns:
        Нормализованный email в нижнем регистре.

    Raises:
        DomainError: Если email отсутствует или
            некорректен.
    """
    if not email:
        raise DomainError(
            'Укажите email для обратной связи',
            'EMAIL_REQUIRED',
        )
    cleaned = email.strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise DomainError(
            'Некорректный формат email',
            'INVALID_EMAIL',
        )
    return cleaned


@log
async def handle_create_support_ticket_command(
    command: commands.CreateSupportTicketCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SupportTicketResponse:
    """
    Создаёт обращение в техподдержку.

    Для авторизованных берёт email из профиля; для
    гостей требует валидный email. Учитывает дневной
    антиспам-лимит.

    Args:
        command: subject, body, email, user_uid и
            client_ip.
        uow: Unit of Work текущего запроса.

    Returns:
        SupportTicketResponse с id и статусом.

    Raises:
        DomainError: Пустые/длинные поля, нет email
            или неверный формат.
        EntityNotFoundError: Если пользователь не
            найден или неактивен.
        PermissionDeniedError: Если email не совпадает
            с профилем.
        RateLimitExceededError: Если превышен дневной
            лимит обращений.
    """
    subject = _require_non_empty(command.subject, 'Тема')
    body = _require_non_empty(command.body, 'Текст')
    if len(subject) > 200:
        raise DomainError(
            'Тема слишком длинная (макс. 200 символов)',
            'SUBJECT_TOO_LONG',
        )
    if len(body) > 5000:
        raise DomainError(
            'Текст слишком длинный (макс. 5000 символов)',
            'BODY_TOO_LONG',
        )

    user_uid: uuid.UUID | None = command.user_uid
    if user_uid is not None:
        user = await uow.user_repository.get_by_id(user_uid)
        if user is None or not user.is_active:
            raise EntityNotFoundError('User', user_uid)
        if not user.email:
            raise DomainError(
                'В профиле не указан email. '
                'Добавьте email в аккаунте и повторите.',
                'NO_EMAIL',
            )
        effective_email = user.email.strip().lower()
        if (
            command.email
            and command.email.strip().lower()
            != effective_email
        ):
            raise PermissionDeniedError(
                'Авторизованный пользователь может '
                'отправить обращение только с email '
                'из профиля.',
            )
    else:
        effective_email = _validate_guest_email(command.email)

    client_ip = (command.client_ip or '').strip() or None

    await check_support_ticket_daily_limit(
        uow,
        user_uid=user_uid,
        email=effective_email,
        client_ip=client_ip,
    )

    ticket = SupportTicket(
        user_id=user_uid,
        email=effective_email,
        subject=subject,
        body=body,
        status='new',
        client_ip=client_ip,
    )
    ticket = await uow.support_ticket_repository.add(ticket)
    await uow.commit()

    logger.info(
        'Обращение в техподдержку #%s от %s',
        ticket.id,
        effective_email,
    )
    return SupportTicketResponse(
        id=ticket.id,
        status=ticket.status,
        created_at=ticket.created_at,
        message=(
            'Обращение отправлено. '
            'Мы ответим на указанный email.'
        ),
    )
