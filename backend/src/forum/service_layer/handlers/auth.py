"""Handlers auth: upsert пользователя из Keycloak claims."""

import uuid

from general.logger import log

from forum.domain import commands
from forum.domain.schemas.users import UserResponse
from forum.service_layer import unit_of_work
from forum.service_layer.handlers.visitors import (
    merge_guest_on_login,
)


def make_initials(display_name: str) -> str:
    """
    Строит инициалы для аватара из отображаемого имени.

    Берёт первые буквы двух слов или первые 2 символа
    одного слова; иначе '??'. Обрезка до 8 символов.

    Args:
        display_name: Имя пользователя.

    Returns:
        Строка инициалов в верхнем регистре.
    """
    parts = [p for p in display_name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()[:8]
    if parts:
        return parts[0][:2].upper()
    return '??'


def ensure_user_command_from_keycloak(
    user_info: dict,
    *,
    anon_id: str | None = None,
) -> commands.EnsureUserCommand:
    """
    Маппит Keycloak userinfo/JWT claims в EnsureUserCommand.

    sub → uid; preferred_username/email/sub → username;
    name или username → display_name; picture → avatar_url.

    Args:
        user_info: Словарь claims (sub обязателен).
        anon_id: Cookie гостя для merge.

    Returns:
        EnsureUserCommand для MessageBus.

    Raises:
        ValueError: Если нет claim sub.
    """
    sub = user_info.get('sub')
    if not sub:
        raise ValueError('ID пользователя не найден')

    username = (
        user_info.get('preferred_username')
        or user_info.get('email')
        or str(sub)
    )
    display_name = user_info.get('name') or username

    return commands.EnsureUserCommand(
        uid=uuid.UUID(str(sub)),
        username=username,
        email=user_info.get('email'),
        email_verified=bool(
            user_info.get('email_verified', False),
        ),
        display_name=display_name,
        avatar_url=user_info.get('picture'),
        anon_id=anon_id,
    )


@log
async def handle_ensure_user_command(
    command: commands.EnsureUserCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UserResponse:
    """
    Находит или создаёт пользователя из claims Keycloak.

    При наличии anon_id промоутит гостевую запись
    и мержит статистику визитов.

    Args:
        command: uid, username, email, display_name,
            avatar_url и опциональный anon_id.
        uow: Unit of Work текущего запроса.

    Returns:
        UserResponse созданного или обновлённого
        пользователя.
    """
    return await merge_guest_on_login(
        command,
        uow,
        anon_id=command.anon_id,
    )
