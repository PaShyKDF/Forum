import uuid
from dataclasses import dataclass

from forum.domain.commands.base import Command


@dataclass
class TrackGuestVisitCommand(Command):
    """Трекинг анонимного визита по cookie."""

    anon_id: str | None
    user_agent: str | None
    is_authenticated: bool
    client_ip: str | None = None
    # Для авторизованных: обновление presence с throttle
    user_uid: uuid.UUID | None = None


@dataclass
class TrackGuestVisitResult:
    """Результат трекинга: нужно ли поставить cookie."""

    anon_id: str | None
    set_cookie: bool
