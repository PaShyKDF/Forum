from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetTopicsCommand(Command):
    """Команда списка тем с фильтрами."""

    category_id: int | None = None
    is_topic: bool | None = None
    # 'active' | 'participated' | None
    filter_by: str | None = None
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class GetTopicByIdCommand(Command):
    """Команда получения темы со сообщениями."""

    topic_id: int
    page: int = 1
    page_size: int | None = None
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class CreateTopicCommand(Command):
    """Создать тему с первым сообщением."""

    category_id: int
    author_id: uuid.UUID
    title: str
    body: str
    description: str | None = None
    is_restricted: bool = False
    allowed_user_uids: list[uuid.UUID] | None = None
    is_admin: bool = False


@dataclass
class UpdateTopicTitleCommand(Command):
    """Изменить название темы в окне редактирования."""

    topic_id: int
    author_id: uuid.UUID
    title: str
    is_admin: bool = False


@dataclass
class RecordTopicViewCommand(Command):
    """Засчитать просмотр темы зрителем за сутки."""

    topic_id: int
    user_uid: uuid.UUID | None = None
    anon_id: str | None = None
