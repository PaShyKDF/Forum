"""Команды управления ACL и видимостью."""

from dataclasses import dataclass, field
import uuid

from forum.domain.commands.base import Command


@dataclass
class SetCategoryMembersCommand(Command):
    """Заменить whitelist пользователей категории."""

    category_id: int
    user_uids: list[uuid.UUID]
    actor_uid: uuid.UUID
    is_admin: bool = False


@dataclass
class SetTopicMembersCommand(Command):
    """Заменить whitelist пользователей темы."""

    topic_id: int
    user_uids: list[uuid.UUID]
    actor_uid: uuid.UUID
    is_admin: bool = False


@dataclass
class GetCategoryMembersCommand(Command):
    """Список допущенных к категории."""

    category_id: int
    is_admin: bool = False


@dataclass
class GetTopicMembersCommand(Command):
    """Список допущенных к теме."""

    topic_id: int
    is_admin: bool = False


@dataclass
class SetCategoryVisibilityCommand(Command):
    """Скрыть/открыть категорию (is_restricted)."""

    category_id: int
    is_restricted: bool
    actor_uid: uuid.UUID
    is_admin: bool = False


@dataclass
class SetTopicVisibilityCommand(Command):
    """Скрыть/открыть тему (is_restricted)."""

    topic_id: int
    is_restricted: bool
    actor_uid: uuid.UUID
    is_admin: bool = False


@dataclass
class SearchUsersCommand(Command):
    """Поиск пользователей для picker."""

    query: str
    limit: int = 20
    is_admin: bool = False


@dataclass
class CreateRestrictedTopicCommand(Command):
    """Создать тему (опционально скрытую) админом."""

    category_id: int
    author_id: uuid.UUID
    title: str
    body: str
    description: str | None = None
    is_restricted: bool = False
    allowed_user_uids: list[uuid.UUID] = field(
        default_factory=list,
    )
    is_admin: bool = False
