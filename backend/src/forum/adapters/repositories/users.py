"""Репозиторий пользователей форума."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import User
from forum.domain.schemas.users import UserCreate


class UserRepository(SQLAlchemyRepository[User, uuid.UUID]):
    """Репозиторий пользователей форума."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_id(
        self,
        entity_id: uuid.UUID,
    ) -> User | None:
        """
        Пользователь по uid (PK).

        Args:
            entity_id: UUID пользователя (Keycloak sub
                или гостевой uid).

        Returns:
            User или None, если не найден.
        """
        stmt = select(User).where(User.uid == entity_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_avatar(
        self,
        entity_id: uuid.UUID,
    ) -> User | None:
        """
        Пользователь с загруженным avatar_blob.

        avatar_blob обычно deferred; здесь снимается
        отложенная загрузка через undefer.

        Args:
            entity_id: UUID пользователя.

        Returns:
            User с avatar_blob или None.
        """
        stmt = (
            select(User)
            .where(User.uid == entity_id)
            .options(undefer(User.avatar_blob))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        """
        Создаёт пользователя из schema.

        Args:
            data: UserCreate с полями новой записи.

        Returns:
            Сохранённый User (после flush/refresh).
        """
        entity = User(**data.model_dump())
        return await self.add(entity)

    async def delete(self, entity_id: uuid.UUID) -> bool:
        """
        Удаляет пользователя по uid.

        Args:
            entity_id: UUID пользователя.

        Returns:
            True, если строка была удалена.
        """
        stmt = delete(User).where(User.uid == entity_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def exists(self, entity_id: uuid.UUID) -> bool:
        """
        Проверяет наличие пользователя с данным uid.

        Args:
            entity_id: UUID пользователя.

        Returns:
            True, если запись существует.
        """
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.uid == entity_id)
        )
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        return count > 0

    async def count_active_users(self) -> int:
        """
        Число активных зарегистрированных пользователей.

        Учитывает is_active=True и is_guest=False.

        Returns:
            Количество подходящих записей User.
        """
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                User.is_active.is_(True),
                User.is_guest.is_(False),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def search_registered(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[User]:
        """
        Поиск зарегистрированных пользователей по
        нику/логину/email.

        Пустой query — первые N пользователей
        (для ACL-picker). limit ограничивается 1..50.

        Args:
            query: подстрока поиска (ilike) или пустая.
            limit: максимум результатов (по умолчанию 20).

        Returns:
            Список активных не-гостевых User.
        """
        cleaned = (query or '').strip()
        safe_limit = max(1, min(limit, 50))
        conditions = [
            User.is_active.is_(True),
            User.is_guest.is_(False),
        ]
        if cleaned:
            pattern = f'%{cleaned}%'
            conditions.append(
                User.display_name.ilike(pattern)
                | User.username.ilike(pattern)
                | User.email.ilike(pattern),
            )
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.display_name.asc())
            .limit(safe_limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_active_since(
        self,
        since_utc: datetime,
    ) -> int:
        """
        Активные записи (гости + аккаунты) с last_seen_at
        не раньше since_utc.

        Args:
            since_utc: нижняя граница last_seen_at (UTC).

        Returns:
            Число активных User с last_seen_at >= since_utc.
        """
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                User.is_active.is_(True),
                User.last_seen_at.is_not(None),
                User.last_seen_at >= since_utc,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_by_anon_id(
        self,
        anon_id: str,
    ) -> User | None:
        """
        Активный гость по anon_id cookie.

        Args:
            anon_id: значение анонимной cookie.

        Returns:
            Гостевой User или None.
        """
        stmt = select(User).where(
            User.anon_id == anon_id,
            User.is_guest.is_(True),
            User.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_guest(
        self,
        *,
        anon_id: str,
        seen_at: datetime,
        ip: str | None = None,
        country: str | None = None,
        city: str | None = None,
    ) -> User:
        """
        Создаёт гостевую запись в таблице user.

        username вида guest-{8 символов anon_id},
        display_name «Гость».

        Args:
            anon_id: уникальный anon_id cookie.
            seen_at: начальный last_seen_at.
            ip: последний IP клиента или None.
            country: страна по geo или None.
            city: город по geo или None.

        Returns:
            Сохранённый гостевой User.
        """
        short = anon_id.replace('-', '')[:8]
        entity = User(
            uid=uuid.uuid4(),
            username=f'guest-{short}',
            email=None,
            email_verified=False,
            display_name='Гость',
            initials='Г',
            avatar_url=None,
            anon_id=anon_id,
            is_guest=True,
            registered_at=None,
            last_seen_at=seen_at,
            last_ip=ip,
            last_country=country,
            last_city=city,
            last_ip_at=seen_at if ip else None,
        )
        return await self.add(entity)

    async def touch_last_seen(
        self,
        uid: uuid.UUID,
        seen_at: datetime,
    ) -> User | None:
        """
        Обновляет время последнего визита.

        Args:
            uid: UUID пользователя.
            seen_at: новое значение last_seen_at.

        Returns:
            Обновлённый User или None, если не найден.
        """
        return await self.touch_presence(uid, seen_at=seen_at)

    async def touch_presence(
        self,
        uid: uuid.UUID,
        *,
        seen_at: datetime,
        ip: str | None = None,
        country: str | None = None,
        city: str | None = None,
    ) -> User | None:
        """
        Обновляет last_seen и опционально IP/гео.

        Args:
            uid: UUID пользователя.
            seen_at: новое значение last_seen_at.
            ip: IP клиента или None (не трогать IP).
            country: страна или None (не трогать).
            city: город или None (не трогать).

        Returns:
            Обновлённый User или None, если не найден.
        """
        user = await self.get_by_id(uid)
        if user is None:
            return None
        user.last_seen_at = seen_at
        if ip is not None:
            ip_changed = user.last_ip != ip
            user.last_ip = ip
            if country is not None:
                user.last_country = country
            if city is not None:
                user.last_city = city
            if (
                ip_changed
                or country is not None
                or city is not None
            ):
                user.last_ip_at = seen_at
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete_guest(
        self,
        anon_id: str,
    ) -> bool:
        """
        Удаляет активного гостя (после merge-конфликта).

        Args:
            anon_id: anon_id cookie гостя.

        Returns:
            True, если гость найден и удалён.
        """
        guest = await self.get_by_anon_id(anon_id)
        if guest is None or not guest.is_guest:
            return False
        await self.session.delete(guest)
        await self.session.flush()
        return True

    async def promote_guest_to_registered(
        self,
        *,
        anon_id: str,
        keycloak_uid: uuid.UUID,
        username: str,
        email: str | None,
        email_verified: bool,
        display_name: str,
        initials: str,
        avatar_url: str | None,
        registered_at: datetime,
    ) -> User | None:
        """
        Превращает гостевую строку в зарегистрированную.

        Меняет PK uid на Keycloak sub через SQL UPDATE
        (объект снимается из identity map перед сменой PK).

        Args:
            anon_id: anon_id текущего гостя.
            keycloak_uid: новый uid (Keycloak sub).
            username: логин из IdP.
            email: email или None.
            email_verified: флаг подтверждения email.
            display_name: отображаемое имя.
            initials: инициалы для аватара-заглушки.
            avatar_url: URL аватара или None.
            registered_at: момент регистрации.

        Returns:
            Зарегистрированный User или None, если гостя нет.
        """
        guest = await self.get_by_anon_id(anon_id)
        if guest is None or not guest.is_guest:
            return None

        old_uid = guest.uid
        last_seen = guest.last_seen_at
        # Снимаем объект из identity map перед сменой PK
        await self.session.flush()
        self.session.expunge(guest)
        await self.session.execute(
            text(
                'UPDATE "user" SET '
                'uid = :new_uid, '
                'username = :username, '
                'email = :email, '
                'email_verified = :email_verified, '
                'display_name = :display_name, '
                'initials = :initials, '
                'avatar_url = :avatar_url, '
                'is_guest = false, '
                'anon_id = NULL, '
                'registered_at = :registered_at, '
                'last_seen_at = :last_seen_at, '
                'is_active = true '
                'WHERE uid = :old_uid AND is_guest = true'
            ),
            {
                'new_uid': str(keycloak_uid),
                'old_uid': str(old_uid),
                'username': username,
                'email': email,
                'email_verified': email_verified,
                'display_name': display_name,
                'initials': initials,
                'avatar_url': avatar_url,
                'registered_at': registered_at,
                'last_seen_at': last_seen or registered_at,
            },
        )
        self.session.expire_all()
        return await self.get_by_id(keycloak_uid)

    async def update_display_name(
        self,
        uid: uuid.UUID,
        display_name: str,
        initials: str,
    ) -> User | None:
        """
        Обновляет никнейм и инициалы.

        Args:
            uid: UUID пользователя.
            display_name: новое отображаемое имя.
            initials: новые инициалы.

        Returns:
            Обновлённый User или None.
        """
        user = await self.get_by_id(uid)
        if user is None:
            return None
        user.display_name = display_name
        user.initials = initials
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_avatar_blob(
        self,
        uid: uuid.UUID,
        content: bytes,
        mime_type: str,
    ) -> User | None:
        """
        Сохраняет фото аватара в БД.

        Выставляет avatar_url на /api/users/{uid}/avatar.

        Args:
            uid: UUID пользователя.
            content: бинарные данные изображения.
            mime_type: MIME-тип (например, image/png).

        Returns:
            User с обновлённым аватаром или None.
        """
        user = await self.get_with_avatar(uid)
        if user is None:
            return None
        user.avatar_blob = content
        user.avatar_mime = mime_type
        user.avatar_url = f'/api/users/{uid}/avatar'
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def clear_avatar(
        self,
        uid: uuid.UUID,
    ) -> User | None:
        """
        Удаляет фото аватара.

        Обнуляет avatar_blob, avatar_mime и avatar_url.

        Args:
            uid: UUID пользователя.

        Returns:
            User без аватара или None.
        """
        user = await self.get_with_avatar(uid)
        if user is None:
            return None
        user.avatar_blob = None
        user.avatar_mime = None
        user.avatar_url = None
        await self.session.flush()
        await self.session.refresh(user)
        return user
