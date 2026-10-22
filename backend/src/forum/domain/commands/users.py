"""Команды CQRS для профиля пользователя."""

from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetCurrentUserProfileCommand(Command):
    """Профиль текущего пользователя со статистикой."""

    user_uid: uuid.UUID


@dataclass
class GetPublicUserProfileCommand(Command):
    """Публичный профиль пользователя по uid."""

    user_uid: uuid.UUID


@dataclass
class UpdateUserProfileCommand(Command):
    """Обновление отображаемого имени."""

    user_uid: uuid.UUID
    display_name: str


@dataclass
class UploadUserAvatarCommand(Command):
    """Загрузка фото аватара в БД."""

    user_uid: uuid.UUID
    content: bytes
    mime_type: str


@dataclass
class DeleteUserAvatarCommand(Command):
    """Удаление фото аватара из БД."""

    user_uid: uuid.UUID


@dataclass
class GetUserAvatarCommand(Command):
    """Получение байтов аватара пользователя."""

    user_uid: uuid.UUID
