import uuid
from dataclasses import dataclass

from forum.domain.commands.base import Command


@dataclass
class EnsureUserCommand(Command):
    """Создать пользователя из Keycloak, если его ещё нет."""

    uid: uuid.UUID
    username: str
    email: str | None
    email_verified: bool
    display_name: str
    avatar_url: str | None = None
    # Cookie гостя для merge при первом логине
    anon_id: str | None = None
    client_ip: str | None = None
