"""Unit of Work: одна транзакция и доступ к репозиториям."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from general.logger import logger

from forum.adapters.repositories import (
    CategoryRepository,
    ContentAclRepository,
    DirectChatRepository,
    DirectMessageRepository,
    PostRepository,
    SectionRepository,
    SupportTicketRepository,
    TopicNotificationRepository,
    TopicRepository,
    TopicViewRepository,
    UserRepository,
)
from forum.config import configuration
from forum.domain.events import Event


if configuration.mode.mode == 'TEST':
    DATABASE_PARAMS = {'poolclass': NullPool}
    DATABASE_URL = configuration.test_db.database_async_url
else:
    DATABASE_PARAMS = {
        'pool_size': configuration.db.pool_size,
        'max_overflow': configuration.db.max_overflow,
    }
    DATABASE_URL = configuration.db.database_async_url

async_engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    **DATABASE_PARAMS,
)
DEFAULT_SESSION_FACTORY = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    close_resets_only=False,
)


class AbstractUnitOfWork(ABC):
    """
    Контракт Unit of Work для сервисного слоя.

    Держит репозитории и очередь доменных событий в рамках
    одной транзакции.
    """

    events: list[Event]
    section_repository: SectionRepository
    category_repository: CategoryRepository
    topic_repository: TopicRepository
    post_repository: PostRepository
    user_repository: UserRepository
    content_acl_repository: ContentAclRepository
    chat_repository: DirectChatRepository
    chat_message_repository: DirectMessageRepository
    support_ticket_repository: SupportTicketRepository
    notification_repository: TopicNotificationRepository
    topic_view_repository: TopicViewRepository

    @abstractmethod
    async def __aenter__(self) -> Self:
        """
        Открывает сессию и инициализирует репозитории.

        Returns:
            Этот же экземпляр UoW.
        """
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Закрывает сессию; при исключении делает rollback.

        Args:
            exc_type: Тип исключения или None.
            exc_val: Экземпляр исключения или None.
            exc_tb: Трейсбек или None.

        Returns:
            False — исключение не подавляется.
        """
        raise NotImplementedError

    @abstractmethod
    async def commit(self):
        """Фиксирует текущую транзакцию сессии."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        """Откатывает текущую транзакцию сессии."""
        raise NotImplementedError

    @abstractmethod
    async def refresh(self, obj):
        """
        Перечитывает объект из БД в текущей сессии.

        Args:
            obj: ORM-сущность, уже привязанная к сессии.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, obj):
        """
        Помечает объект к удалению в текущей сессии.

        Args:
            obj: ORM-сущность для удаления.
        """
        raise NotImplementedError

    @abstractmethod
    async def save_event(self, event: Event):
        """
        Кладёт доменное событие в очередь UoW.

        Args:
            event: Экземпляр доменного Event.
        """
        raise NotImplementedError

    @abstractmethod
    async def collect_new_events(
        self,
        timeout: int = 1,
    ) -> list[Event]:
        """
        Забирает и очищает накопленные события.

        Args:
            timeout: Зарезервировано API (не используется).

        Returns:
            Список событий, накопленных с прошлого collect.
        """
        raise NotImplementedError


class UnitOfWork(AbstractUnitOfWork):
    """
    SQLAlchemy-реализация Unit of Work.

    Создаёт AsyncSession, репозитории и очередь events
    на время `async with`.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker = (
            DEFAULT_SESSION_FACTORY
        ),
    ):
        """
        Args:
            session_factory: Фабрика async-сессий SQLAlchemy.
        """
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.events: list[Event] = []

    async def __aenter__(self):
        """
        Открывает сессию и инициализирует репозитории.

        Returns:
            Этот же экземпляр UoW.
        """
        logger.debug('Создание сессии')
        self.session = self._session_factory()
        self.section_repository = SectionRepository(
            self.session,
        )
        self.category_repository = CategoryRepository(
            self.session,
        )
        self.topic_repository = TopicRepository(self.session)
        self.post_repository = PostRepository(self.session)
        self.user_repository = UserRepository(self.session)
        self.content_acl_repository = ContentAclRepository(
            self.session,
        )
        self.chat_repository = DirectChatRepository(
            self.session,
        )
        self.chat_message_repository = (
            DirectMessageRepository(self.session)
        )
        self.support_ticket_repository = (
            SupportTicketRepository(self.session)
        )
        self.notification_repository = (
            TopicNotificationRepository(self.session)
        )
        self.topic_view_repository = TopicViewRepository(
            self.session,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Закрывает сессию; при исключении делает rollback.

        Args:
            exc_type: Тип исключения или None.
            exc_val: Экземпляр исключения или None.
            exc_tb: Трейсбек или None.

        Returns:
            False — исключение не подавляется.
        """
        if exc_type:
            await self.rollback()

        if self.session:
            logger.debug('Закрытие сессии')
            await self.session.close()

        return False

    def _ensure_session(self) -> AsyncSession:
        """
        Возвращает открытую сессию или падает.

        Returns:
            Текущая AsyncSession.

        Raises:
            RuntimeError: Если UoW используется вне
                контекста `async with`.
        """
        if not hasattr(self, 'session') or self.session is None:
            raise RuntimeError(
                'Сессия не инициализирована. '
                'Используйте UnitOfWork в контексте '
                '"async with"'
            )
        return self.session

    async def commit(self):
        """Фиксирует текущую транзакцию сессии."""
        session = self._ensure_session()
        logger.debug('Фиксация транзакции')
        await session.commit()

    async def rollback(self):
        """Откатывает текущую транзакцию сессии."""
        session = self._ensure_session()
        logger.debug('Откат транзакции')
        await session.rollback()

    async def refresh(self, obj):
        """
        Перечитывает объект из БД в текущей сессии.

        Args:
            obj: ORM-сущность, уже привязанная к сессии.
        """
        session = self._ensure_session()
        logger.debug('Обновление объекта из БД')
        await session.refresh(obj)

    async def delete(self, obj):
        """
        Помечает объект к удалению в текущей сессии.

        Args:
            obj: ORM-сущность для удаления.
        """
        session = self._ensure_session()
        logger.debug('Удаление объекта из БД')
        await session.delete(obj)

    async def save_event(self, event: Event):
        """
        Кладёт доменное событие в очередь UoW.

        Args:
            event: Экземпляр доменного Event.
        """
        logger.debug(f'Сохранение события: {event}')
        self.events.append(event)

    async def collect_new_events(
        self,
        timeout: int = 1,
    ) -> list[Event]:
        """
        Забирает и очищает накопленные события.

        Args:
            timeout: Зарезервировано API (не используется).

        Returns:
            Список событий, накопленных с прошлого collect.
        """
        events = self.events.copy()
        self.events.clear()
        logger.debug(f'Собрано событий: {len(events)}')
        return events


async def get_unit_of_work() -> AsyncGenerator[UnitOfWork, None]:
    """
    FastAPI-зависимость: UoW на время запроса.

    Yields:
        Открытый UnitOfWork; закрывается после ответа.
    """
    async with UnitOfWork() as uow:
        yield uow
