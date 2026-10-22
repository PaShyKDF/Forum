"""Репозиторий обращений в техподдержку."""

from datetime import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import SupportTicket


class SupportTicketRepository(
    SQLAlchemyRepository[SupportTicket, int],
):
    """CRUD и счётчики лимитов для SupportTicket."""

    def __init__(self, session: AsyncSession):
        super().__init__(SupportTicket, session)

    async def count_by_user_since(
        self,
        user_id: uuid.UUID,
        since: datetime,
    ) -> int:
        """
        Число обращений пользователя с момента since.

        Используется для rate-limit по user_id.

        Args:
            user_id: UUID автора обращений.
            since: нижняя граница created_at.

        Returns:
            Количество SupportTicket.
        """
        stmt = select(func.count(SupportTicket.id)).where(
            SupportTicket.user_id == user_id,
            SupportTicket.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_email_since(
        self,
        email: str,
        since: datetime,
    ) -> int:
        """
        Число обращений с email с момента since.

        Используется для rate-limit по email.

        Args:
            email: адрес отправителя.
            since: нижняя граница created_at.

        Returns:
            Количество SupportTicket.
        """
        stmt = select(func.count(SupportTicket.id)).where(
            SupportTicket.email == email,
            SupportTicket.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_ip_since(
        self,
        client_ip: str,
        since: datetime,
    ) -> int:
        """
        Число обращений с IP с момента since.

        Используется для rate-limit по client_ip.

        Args:
            client_ip: IP клиента.
            since: нижняя граница created_at.

        Returns:
            Количество SupportTicket.
        """
        stmt = select(func.count(SupportTicket.id)).where(
            SupportTicket.client_ip == client_ip,
            SupportTicket.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
