from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetHomeCommand(Command):
    """Команда получения контента главной страницы."""

    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class GetCategoriesCommand(Command):
    """Команда списка категорий с фильтром section_id."""

    section_id: int | None = None
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class GetCategoryByIdCommand(Command):
    """Команда получения категории с темами."""

    category_id: int
    current_user_uid: uuid.UUID | None = None
    is_admin: bool = False


@dataclass
class CreateCategoryCommand(Command):
    """Создать категорию в разделе (только админ)."""

    section_id: int
    title: str
    description: str | None = None
    is_restricted: bool = False
    allowed_user_uids: list[uuid.UUID] | None = None
    is_admin: bool = False
