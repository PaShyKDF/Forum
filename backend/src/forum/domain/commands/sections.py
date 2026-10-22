"""Команды разделов форума."""

from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetSectionsCommand(Command):
    """Команда списка разделов с фильтром is_topic."""

    is_topic: bool | None = None


@dataclass
class GetSectionByIdCommand(Command):
    """Команда получения раздела с категориями."""

    section_id: int
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False
