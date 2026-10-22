"""Репозиторий личных чатов и сообщений."""

from datetime import datetime
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import DirectChat, DirectMessage
from forum.service_layer.timeutils import utc_now_naive


def normalize_pair(
    uid_a: uuid.UUID,
    uid_b: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    """
    Нормализует пару участников чата.

    Порядок по строковому сравнению UUID, чтобы пара
    (A, B) и (B, A) давала один ключ (low, high).

    Args:
        uid_a: UUID первого участника.
        uid_b: UUID второго участника.

    Returns:
        Кортеж (user_low_id, user_high_id).
    """
    if str(uid_a) <= str(uid_b):
        return uid_a, uid_b
    return uid_b, uid_a


class DirectChatRepository(
    SQLAlchemyRepository[DirectChat, int],
):
    """Репозиторий диалогов 1-на-1."""

    def __init__(self, session: AsyncSession):
        super().__init__(DirectChat, session)

    async def get_by_pair(
        self,
        uid_a: uuid.UUID,
        uid_b: uuid.UUID,
    ) -> DirectChat | None:
        """
        Активный чат по паре участников.

        Порядок uid не важен: пара нормализуется.

        Args:
            uid_a: UUID первого участника.
            uid_b: UUID второго участника.

        Returns:
            DirectChat с user_low/user_high или None.
        """
        low, high = normalize_pair(uid_a, uid_b)
        stmt = (
            select(DirectChat)
            .where(
                DirectChat.user_low_id == low,
                DirectChat.user_high_id == high,
                DirectChat.is_active.is_(True),
            )
            .options(
                selectinload(DirectChat.user_low),
                selectinload(DirectChat.user_high),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_direct_chat(
        self,
        current_uid: uuid.UUID,
        other_uid: uuid.UUID,
    ) -> DirectChat:
        """
        Находит или создаёт диалог между двумя
        пользователями.

        После создания перечитывает чат для current_uid
        с подгруженными участниками.

        Args:
            current_uid: UUID текущего пользователя.
            other_uid: UUID собеседника.

        Returns:
            Существующий или новый DirectChat.
        """
        existing = await self.get_by_pair(current_uid, other_uid)
        if existing is not None:
            return existing

        low, high = normalize_pair(current_uid, other_uid)
        chat = DirectChat(
            user_low_id=low,
            user_high_id=high,
        )
        await self.add(chat)
        await self.session.flush()
        loaded = await self.get_chat_for_user(
            chat.id,
            current_uid,
        )
        return loaded or chat

    async def get_chat_for_user(
        self,
        chat_id: int,
        user_uid: uuid.UUID,
    ) -> DirectChat | None:
        """
        Активный чат, если user_uid — участник.

        Иначе None (нет доступа / нет чата).

        Args:
            chat_id: ID диалога.
            user_uid: UUID предполагаемого участника.

        Returns:
            DirectChat с участниками или None.
        """
        stmt = (
            select(DirectChat)
            .where(
                DirectChat.id == chat_id,
                DirectChat.is_active.is_(True),
                or_(
                    DirectChat.user_low_id == user_uid,
                    DirectChat.user_high_id == user_uid,
                ),
            )
            .options(
                selectinload(DirectChat.user_low),
                selectinload(DirectChat.user_high),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_chats(
        self,
        user_uid: uuid.UUID,
    ) -> list[DirectChat]:
        """
        Чаты пользователя, новые сверху по updated_at.

        Args:
            user_uid: UUID участника.

        Returns:
            Список активных DirectChat с участниками.
        """
        stmt = (
            select(DirectChat)
            .where(
                DirectChat.is_active.is_(True),
                or_(
                    DirectChat.user_low_id == user_uid,
                    DirectChat.user_high_id == user_uid,
                ),
            )
            .options(
                selectinload(DirectChat.user_low),
                selectinload(DirectChat.user_high),
            )
            .order_by(DirectChat.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def touch_updated_at(self, chat_id: int) -> None:
        """
        Обновляет updated_at чата после нового сообщения.

        Args:
            chat_id: ID диалога.
        """
        chat = await self.get_by_id(chat_id)
        if chat is None:
            return
        chat.updated_at = utc_now_naive()
        await self.session.flush()


class DirectMessageRepository(
    SQLAlchemyRepository[DirectMessage, int],
):
    """Репозиторий сообщений личных чатов."""

    def __init__(self, session: AsyncSession):
        super().__init__(DirectMessage, session)

    async def create_message(
        self,
        chat_id: int,
        sender_id: uuid.UUID,
        body: str,
        *,
        kind: str = 'text',
    ) -> DirectMessage:
        """
        Создаёт сообщение в чате.

        После add перечитывает запись с sender.

        Args:
            chat_id: ID диалога.
            sender_id: UUID отправителя.
            body: текст сообщения.
            kind: тип сообщения (по умолчанию text).

        Returns:
            DirectMessage с подгруженным sender.
        """
        message = DirectMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            body=body,
            kind=kind,
        )
        message = await self.add(message)
        stmt = (
            select(DirectMessage)
            .where(DirectMessage.id == message.id)
            .options(selectinload(DirectMessage.sender))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_messages(
        self,
        chat_id: int,
        *,
        limit: int = 50,
        before_id: int | None = None,
    ) -> list[DirectMessage]:
        """
        Сообщения чата (новые снизу для UI).

        При before_id возвращает более старые сообщения
        (id < before_id). Итог разворачивается по id ASC.

        Args:
            chat_id: ID диалога.
            limit: максимум сообщений (по умолчанию 50).
            before_id: курсор «старше этого id» или None.

        Returns:
            Список активных DirectMessage с sender.
        """
        stmt = (
            select(DirectMessage)
            .where(
                DirectMessage.chat_id == chat_id,
                DirectMessage.is_active.is_(True),
            )
            .options(selectinload(DirectMessage.sender))
        )
        if before_id is not None:
            stmt = stmt.where(DirectMessage.id < before_id)
        stmt = stmt.order_by(DirectMessage.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().unique().all())
        items.reverse()
        return items

    async def count_messages(self, chat_id: int) -> int:
        """
        Число активных сообщений в чате.

        Args:
            chat_id: ID диалога.

        Returns:
            Количество активных DirectMessage.
        """
        stmt = select(func.count(DirectMessage.id)).where(
            DirectMessage.chat_id == chat_id,
            DirectMessage.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_last_message_for_chat_ids(
        self,
        chat_ids: list[int],
    ) -> dict[int, DirectMessage]:
        """
        Последнее сообщение по каждому chat_id.

        Args:
            chat_ids: список ID диалогов.

        Returns:
            Словарь chat_id → последнее DirectMessage.
            Пустой dict при пустом chat_ids.
        """
        if not chat_ids:
            return {}

        stmt = (
            select(DirectMessage)
            .where(
                DirectMessage.chat_id.in_(chat_ids),
                DirectMessage.is_active.is_(True),
            )
            .options(selectinload(DirectMessage.sender))
            .distinct(DirectMessage.chat_id)
            .order_by(
                DirectMessage.chat_id,
                DirectMessage.created_at.desc(),
            )
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().unique().all())
        return {msg.chat_id: msg for msg in messages}

    async def count_unread_for_user(
        self,
        user_uid: uuid.UUID,
    ) -> int:
        """
        Число непрочитанных входящих ЛС пользователя.

        Считает активные сообщения в чатах пользователя,
        где отправитель — не он и read_at пуст.

        Args:
            user_uid: UUID получателя.

        Returns:
            Количество непрочитанных входящих.
        """
        stmt = (
            select(func.count(DirectMessage.id))
            .join(
                DirectChat,
                DirectChat.id == DirectMessage.chat_id,
            )
            .where(
                DirectMessage.is_active.is_(True),
                DirectMessage.read_at.is_(None),
                DirectMessage.sender_id != user_uid,
                DirectChat.is_active.is_(True),
                or_(
                    DirectChat.user_low_id == user_uid,
                    DirectChat.user_high_id == user_uid,
                ),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_unread_by_chat_ids(
        self,
        user_uid: uuid.UUID,
        chat_ids: list[int],
    ) -> dict[int, int]:
        """
        Непрочитанные входящие по каждому чату.

        Args:
            user_uid: UUID получателя.
            chat_ids: ID диалогов для подсчёта.

        Returns:
            Словарь chat_id → число непрочитанных.
            Чаты без непрочитанных не входят в словарь.
        """
        if not chat_ids:
            return {}
        stmt = (
            select(
                DirectMessage.chat_id,
                func.count(DirectMessage.id),
            )
            .where(
                DirectMessage.chat_id.in_(chat_ids),
                DirectMessage.is_active.is_(True),
                DirectMessage.read_at.is_(None),
                DirectMessage.sender_id != user_uid,
            )
            .group_by(DirectMessage.chat_id)
        )
        result = await self.session.execute(stmt)
        return {
            int(chat_id): int(count)
            for chat_id, count in result.all()
        }

    async def mark_visible(
        self,
        *,
        user_uid: uuid.UUID,
        message_ids: list[int],
        read_at: datetime,
    ) -> list[int]:
        """
        Помечает входящие сообщения прочитанными.

        Только сообщения из чатов пользователя, где
        отправитель — не текущий пользователь, и read_at
        пуст.

        Args:
            user_uid: UUID читающего участника.
            message_ids: кандидаты на пометку.
            read_at: время прочтения.

        Returns:
            Список id реально помеченных сообщений.
        """
        if not message_ids:
            return []

        stmt = (
            select(DirectMessage)
            .join(
                DirectChat,
                DirectChat.id == DirectMessage.chat_id,
            )
            .where(
                DirectMessage.id.in_(message_ids),
                DirectMessage.is_active.is_(True),
                DirectMessage.read_at.is_(None),
                DirectMessage.sender_id != user_uid,
                DirectChat.is_active.is_(True),
                or_(
                    DirectChat.user_low_id == user_uid,
                    DirectChat.user_high_id == user_uid,
                ),
            )
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().unique().all())
        marked_ids: list[int] = []
        for message in messages:
            message.read_at = read_at
            marked_ids.append(message.id)
        if marked_ids:
            await self.session.flush()
        return marked_ids
