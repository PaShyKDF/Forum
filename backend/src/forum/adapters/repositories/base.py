"""
Абстрактный базовый репозиторий для DDD архитектуры.

Этот модуль содержит абстрактные классы репозиториев, которые обеспечивают
стандартный интерфейс для работы с данными и инкапсулируют логику доступа
к данным, изолируя доменную логику от деталей хранения.

Ключевые принципы:
- Инкапсуляция логики доступа к данным
- Разделение ответственности между доменом и инфраструктурой
- Поддержка асинхронных операций
- Типизация для лучшей поддержки IDE и статического анализа
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


# Тип переменная для доменных моделей SQLAlchemy
T = TypeVar('T')
# Тип для ID (может быть int, str, UUID и т.д.)
ID = TypeVar('ID', bound=int | str | UUID)


class AbstractRepository(ABC, Generic[T, ID]):
    """
    Абстрактный базовый класс репозитория.

    Определяет стандартный интерфейс для всех репозиториев в приложении.
    Реализует паттерн Repository для изоляции доменной логики от
    деталей хранения данных.

    Type Parameters:
        T: Тип доменной модели (например, Expense, Category)
        ID: Тип идентификатора модели (int, str, UUID и т.д.)
    """

    @abstractmethod
    async def add(self, entity: T) -> T:
        """
        Добавляет новую сущность в репозиторий.

        Args:
            entity: Экземпляр доменной модели для добавления

        Returns:
            T: Добавленная сущность с заполненным ID

        Raises:
            RepositoryError: При ошибке сохранения
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, entity_id: ID) -> T | None:
        """
        Получает сущность по её идентификатору.

        Args:
            entity_id: Идентификатор сущности

        Returns:
            Optional[T]: Найденная сущность или None
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all(
        self, limit: int | None = None, offset: int | None = None
    ) -> list[T]:
        """
        Получает все сущности с возможностью пагинации.

        Args:
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            List[T]: Список найденных сущностей
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Обновляет существующую сущность.

        Args:
            entity: Сущность с обновлёнными данными

        Returns:
            T: Обновлённая сущность

        Raises:
            RepositoryError: При ошибке обновления или если сущность не найдена
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool:
        """
        Удаляет сущность по её идентификатору.

        Args:
            entity_id: Идентификатор сущности для удаления

        Returns:
            bool: True если сущность была удалена, False если не найдена
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(self, entity_id: ID) -> bool:
        """
        Проверяет существование сущности по её идентификатору.

        Args:
            entity_id: Идентификатор сущности

        Returns:
            bool: True если сущность существует, False иначе
        """
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """
        Возвращает общее количество сущностей в репозитории.

        Returns:
            int: Количество сущностей
        """
        raise NotImplementedError


class SQLAlchemyRepository(AbstractRepository[T, ID]):
    """
    Конкретная реализация репозитория для SQLAlchemy.

    Предоставляет базовую реализацию CRUD операций для SQLAlchemy моделей
    с поддержкой асинхронных операций.

    Attributes:
        model: Класс SQLAlchemy модели
        session: Асинхронная сессия SQLAlchemy
    """

    def __init__(self, model: type[T], session: AsyncSession):
        """
        Инициализирует репозиторий.

        Args:
            model: Класс SQLAlchemy модели для работы
            session: Асинхронная сессия SQLAlchemy
        """
        self.model = model
        self.session = session

    async def add(self, entity: T) -> T:
        """
        Добавляет новую сущность в базу данных.

        Args:
            entity: Экземпляр модели для добавления

        Returns:
            T: Добавленная сущность с заполненным ID
        """
        self.session.add(entity)
        await self.session.flush()  # Получаем ID без коммита
        await self.session.refresh(entity)  # Обновляем объект из БД
        return entity

    async def get_by_id(self, entity_id: ID) -> T | None:
        """
        Получает сущность по ID.

        Args:
            entity_id: Идентификатор сущности

        Returns:
            Optional[T]: Найденная сущность или None
        """
        stmt = select(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self, limit: int | None = None, offset: int | None = None
    ) -> list[T]:
        """
        Получает все сущности с пагинацией.

        Args:
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            List[T]: Список найденных сущностей
        """
        stmt = select(self.model)

        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def update(self, entity: T) -> T:
        """
        Обновляет существующую сущность.

        Args:
            entity: Сущность с обновлёнными данными

        Returns:
            T: Обновлённая сущность
        """
        merged_entity = await self.session.merge(entity)
        await self.session.flush()
        await self.session.refresh(merged_entity)
        return merged_entity

    async def delete(self, entity_id: ID) -> bool:
        """
        Удаляет сущность по ID.

        Args:
            entity_id: Идентификатор сущности

        Returns:
            bool: True если удалена, False если не найдена
        """
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def exists(self, entity_id: ID) -> bool:
        """
        Проверяет существование сущности.

        Args:
            entity_id: Идентификатор сущности

        Returns:
            bool: True если существует, False иначе
        """
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.id == entity_id)
        )
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        return count > 0

    async def count(self) -> int:
        """
        Возвращает общее количество сущностей.

        Returns:
            int: Количество сущностей в таблице
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def find_by_criteria(self, **criteria) -> list[T]:
        """
        Находит сущности по заданным критериям.

        Args:
            **criteria: Критерии поиска в формате поле=значение

        Returns:
            List[T]: Список найденных сущностей
        """
        stmt = select(self.model)

        for field, value in criteria.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def find_one_by_criteria(self, **criteria) -> T | None:
        """
        Находит одну сущность по заданным критериям.

        Args:
            **criteria: Критерии поиска в формате поле=значение

        Returns:
            Optional[T]: Найденная сущность или None
        """
        entities = await self.find_by_criteria(**criteria)
        return entities[0] if entities else None

    async def bulk_create(self, entities: list[T]) -> list[T]:
        """
        Массовое создание сущностей.

        Args:
            entities: Список сущностей для создания

        Returns:
            List[T]: Список созданных сущностей
        """
        self.session.add_all(entities)
        await self.session.flush()

        # Обновляем все объекты из БД
        for entity in entities:
            await self.session.refresh(entity)

        return entities

    async def bulk_update(self, updates: list[dict[str, Any]]) -> int:
        """
        Массовое обновление сущностей.

        Args:
            updates: Список словарей с данными для обновления.
                    Каждый словарь должен содержать 'id'
                    и поля для обновления.

        Returns:
            int: Количество обновлённых записей
        """
        total_updated = 0

        for update_data in updates:
            entity_id = update_data.pop('id')
            stmt = (
                update(self.model)
                .where(self.model.id == entity_id)
                .values(**update_data)
            )
            result = await self.session.execute(stmt)
            total_updated += result.rowcount

        await self.session.flush()
        return total_updated

    async def get_with_relations(self, entity_id: ID, *relations) -> T | None:
        """
        Получает сущность с загруженными связями.

        Args:
            entity_id: Идентификатор сущности
            *relations: Имена связей для загрузки

        Returns:
            Optional[T]: Сущность с загруженными связями или None
        """
        stmt = select(self.model).where(self.model.id == entity_id)

        # Добавляем eager loading для указанных связей
        for relation in relations:
            if hasattr(self.model, relation):
                stmt = stmt.options(
                    selectinload(getattr(self.model, relation))
                )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_criteria_with_relationships(
        self, *relations, **criteria
    ) -> list[T]:
        """
        Находит сущности по заданным критериям и со связями.

        Args:
            *relations: Имена связей для загрузки
            **criteria: Критерии поиска в формате поле=значение

        Returns:
            List[T]: Список найденных сущностей
        """

        stmt = select(self.model)

        for field, value in criteria.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)

        for relation in relations:
            if hasattr(self.model, relation):
                stmt = stmt.options(
                    selectinload(getattr(self.model, relation))
                )

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())


class RepositoryError(Exception):
    """
    Базовое исключение для ошибок репозитория.

    Используется для обёртки ошибок, связанных с операциями репозитория,
    чтобы изолировать доменную логику от деталей инфраструктуры.
    """

    def __init__(self, message: str, original_error: Exception | None = None):
        """
        Инициализирует исключение репозитория.

        Args:
            message: Описание ошибки
            original_error: Исходное исключение (если есть)
        """
        super().__init__(message)
        self.original_error = original_error


class EntityNotFoundError(RepositoryError):
    """
    Исключение для случаев, когда сущность не найдена.
    """

    def __init__(self, entity_type: str, entity_id: Any):
        """
        Инициализирует исключение.

        Args:
            entity_type: Тип сущности
            entity_id: Идентификатор сущности
        """
        message = f'{entity_type} с ID {entity_id} не найден'
        super().__init__(message)
        self.entity_type = entity_type
        self.entity_id = entity_id


class DuplicateEntityError(RepositoryError):
    """
    Исключение для случаев дублирования сущности.
    """

    def __init__(self, entity_type: str, field: str, value: Any):
        """
        Инициализирует исключение.

        Args:
            entity_type: Тип сущности
            field: Поле, по которому произошло дублирование
            value: Значение, которое привело к дублированию
        """
        message = f'{entity_type} с {field}={value} уже существует'
        super().__init__(message)
        self.entity_type = entity_type
        self.field = field
        self.value = value
