from dataclasses import dataclass

from forum.domain.commands.base import Command


@dataclass
class TrackGuestVisitCommand(Command):
    """Трекинг анонимного визита по cookie."""

    anon_id: str | None
    user_agent: str | None
    is_authenticated: bool


@dataclass
class TrackGuestVisitResult:
    """Результат трекинга: нужно ли поставить cookie."""

    anon_id: str | None
    set_cookie: bool
