"""Команды CQRS для техподдержки."""

from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class CreateSupportTicketCommand(Command):
    """Создать обращение в техподдержку."""

    subject: str
    body: str
    email: str | None
    user_uid: uuid.UUID | None
    client_ip: str | None
