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


@dataclass
class CreateSectionCommand(Command):
    """Создать раздел (только админ)."""

    title: str
    is_topic: bool = False
    is_admin: bool = False


@dataclass
class UpdateSectionCommand(Command):
    """Обновить название, позицию или шкалу раздела (админ)."""

    section_id: int
    title: str | None = None
    position: int | None = None
    is_topic: bool | None = None
    is_admin: bool = False
