"""Трекинг гостей и merge в зарегистрированного пользователя."""

import uuid
from datetime import datetime

from fastapi import Response

from forum.config import configuration
from forum.domain import commands
from forum.domain.commands.visitors import TrackGuestVisitResult
from forum.domain.schemas.users import UserResponse
from forum.service_layer import unit_of_work
from forum.service_layer.assemblers import build_user_response
from forum.service_layer.geoip import lookup_geo
from forum.service_layer.timeutils import utc_now_naive
from forum.service_layer.visitor_cookies import (
    clear_anon_cookie,
    new_anon_id,
)
from general.logger import log, logger


_BOT_MARKERS = (
    'bot',
    'spider',
    'crawl',
    'slurp',
    'curl/',
    'wget/',
    'python-requests',
    'httpx',
    'scrapy',
)


def _is_bot_user_agent(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    lowered = user_agent.lower()
    return any(marker in lowered for marker in _BOT_MARKERS)


def _should_touch(
    last_seen_at,
    now,
) -> bool:
    interval = configuration.visitors.touch_interval_seconds
    if last_seen_at is None:
        return True
    elapsed = (now - last_seen_at).total_seconds()
    return elapsed >= interval


async def _geo_for_ip(
    ip: str | None,
    *,
    last_ip: str | None,
    last_country: str | None,
) -> tuple[str | None, str | None]:
    """
    Geo lookup только если IP сменился или geo пустое.

    Returns:
        (country, city) для записи или (None, None).
    """
    if not ip:
        return None, None
    if last_ip == ip and last_country:
        return None, None
    result = await lookup_geo(ip)
    if result is None:
        return None, None
    return result


async def _touch_presence(
    uow: unit_of_work.AbstractUnitOfWork,
    uid: uuid.UUID,
    *,
    now: datetime,
    ip: str | None,
    last_ip: str | None = None,
    last_country: str | None = None,
):
    """Обновляет last_seen и при необходимости IP/гео."""
    country, city = await _geo_for_ip(
        ip,
        last_ip=last_ip,
        last_country=last_country,
    )
    return await uow.user_repository.touch_presence(
        uid,
        seen_at=now,
        ip=ip,
        country=country,
        city=city,
    )


async def _create_guest_with_geo(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    anon_id: str,
    now: datetime,
    ip: str | None,
):
    country, city = await _geo_for_ip(
        ip,
        last_ip=None,
        last_country=None,
    )
    return await uow.user_repository.create_guest(
        anon_id=anon_id,
        seen_at=now,
        ip=ip,
        country=country,
        city=city,
    )


@log
async def handle_track_guest_visit_command(
    command: commands.TrackGuestVisitCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> TrackGuestVisitResult:
    """
    Создаёт/обновляет гостевую запись по anon_id.

    Для авторизованных с user_uid обновляет presence
    (last_seen/IP/geo) с throttle. Ботов пропускает.
    Cookie ставит роутер по set_cookie/anon_id.

    Args:
        command: команда трекинга визита гостя.
        uow: unit of work с репозиториями.

    Returns:
        Результат с anon_id и флагом set_cookie.
    """
    now = utc_now_naive()
    if command.is_authenticated:
        if command.user_uid is not None:
            user = await uow.user_repository.get_by_id(
                command.user_uid,
            )
            if user is not None and _should_touch(
                user.last_seen_at,
                now,
            ):
                await _touch_presence(
                    uow,
                    user.uid,
                    now=now,
                    ip=command.client_ip,
                    last_ip=getattr(user, 'last_ip', None),
                    last_country=getattr(
                        user,
                        'last_country',
                        None,
                    ),
                )
                await uow.commit()
                logger.debug(
                    'Обновлён presence user %s',
                    command.user_uid,
                )
        return TrackGuestVisitResult(
            anon_id=None,
            set_cookie=False,
        )
    if _is_bot_user_agent(command.user_agent):
        return TrackGuestVisitResult(
            anon_id=None,
            set_cookie=False,
        )

    anon_id = command.anon_id
    if anon_id is None:
        anon_id = new_anon_id()

    guest = await uow.user_repository.get_by_anon_id(anon_id)
    if guest is None:
        await _create_guest_with_geo(
            uow,
            anon_id=anon_id,
            now=now,
            ip=command.client_ip,
        )
        await uow.commit()
        logger.info('Создан гость anon_id=%s', anon_id)
        return TrackGuestVisitResult(
            anon_id=anon_id,
            set_cookie=True,
        )

    if not guest.is_guest or not guest.is_active:
        # Cookie указывает на неактивную/не-гостевую запись
        anon_id = new_anon_id()
        await _create_guest_with_geo(
            uow,
            anon_id=anon_id,
            now=now,
            ip=command.client_ip,
        )
        await uow.commit()
        logger.info(
            'Ротация гостя, новый anon_id=%s',
            anon_id,
        )
        return TrackGuestVisitResult(
            anon_id=anon_id,
            set_cookie=True,
        )

    if _should_touch(guest.last_seen_at, now):
        await _touch_presence(
            uow,
            guest.uid,
            now=now,
            ip=command.client_ip,
            last_ip=getattr(guest, 'last_ip', None),
            last_country=getattr(guest, 'last_country', None),
        )
        await uow.commit()
        logger.debug(
            'Обновлён last_seen гостя anon_id=%s',
            anon_id,
        )

    return TrackGuestVisitResult(
        anon_id=anon_id,
        set_cookie=True,
    )


@log
async def merge_guest_on_login(
    command: commands.EnsureUserCommand,
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    anon_id: str | None,
) -> UserResponse:
    """
    Upsert зарегистрированного пользователя с merge гостя.

    Если есть guest по anon_id и ещё нет user с Keycloak uid —
    промоутим гостевую строку. Иначе обычный ensure +
    удаление гостя при конфликте.

    Args:
        command: данные пользователя из Keycloak.
        uow: unit of work с репозиториями.
        anon_id: UUID гостя из cookie или None.

    Returns:
        UserResponse зарегистрированного пользователя.
    """
    now = utc_now_naive()
    existing = await uow.user_repository.get_by_id(
        command.uid,
    )
    guest = None
    if anon_id:
        guest = await uow.user_repository.get_by_anon_id(
            anon_id,
        )

    if existing is not None:
        if (
            guest is not None
            and guest.is_guest
            and guest.uid != existing.uid
        ):
            await uow.user_repository.delete_guest(anon_id)
        user = await _touch_presence(
            uow,
            command.uid,
            now=now,
            ip=command.client_ip,
            last_ip=getattr(existing, 'last_ip', None),
            last_country=getattr(
                existing,
                'last_country',
                None,
            ),
        )
        await uow.commit()
        logger.info(
            'Логин существующего пользователя %s',
            command.uid,
        )
        return build_user_response(user)

    if guest is not None and guest.is_guest:
        # Локальный импорт: избегаем цикла auth ↔ visitors
        from forum.service_layer.handlers.auth import (
            make_initials,
        )

        promoted = (
            await uow.user_repository.promote_guest_to_registered(
                anon_id=anon_id,
                keycloak_uid=command.uid,
                username=command.username,
                email=command.email,
                email_verified=command.email_verified,
                display_name=command.display_name,
                initials=make_initials(command.display_name),
                avatar_url=command.avatar_url,
                registered_at=now,
            )
        )
        if promoted is not None:
            if command.client_ip:
                touched = await _touch_presence(
                    uow,
                    command.uid,
                    now=now,
                    ip=command.client_ip,
                    last_ip=getattr(
                        promoted,
                        'last_ip',
                        None,
                    ),
                    last_country=getattr(
                        promoted,
                        'last_country',
                        None,
                    ),
                )
                if touched is not None:
                    promoted = touched
            await uow.commit()
            logger.info(
                'Гость anon_id=%s -> user %s',
                anon_id,
                command.uid,
            )
            return build_user_response(promoted)

    # Fallback: обычное создание
    from forum.domain.schemas.users import UserCreate
    from forum.service_layer.handlers.auth import (
        make_initials,
    )

    if guest is not None and guest.is_guest:
        await uow.user_repository.delete_guest(anon_id)

    user_data = UserCreate(
        uid=command.uid,
        username=command.username,
        email=command.email,
        email_verified=command.email_verified,
        display_name=command.display_name,
        initials=make_initials(command.display_name),
        avatar_url=command.avatar_url,
    )
    user = await uow.user_repository.create(user_data)
    user.last_seen_at = now
    user.is_guest = False
    user.registered_at = now
    user.anon_id = None
    if command.client_ip:
        country, city = await _geo_for_ip(
            command.client_ip,
            last_ip=None,
            last_country=None,
        )
        user.last_ip = command.client_ip
        user.last_country = country
        user.last_city = city
        user.last_ip_at = now
    await uow.commit()
    logger.info('Создан пользователь: %s', command.uid)
    return build_user_response(user)


def finalize_guest_cookie_after_login(
    response: Response,
) -> None:
    """
    Удаляет guest cookie после успешного логина.

    Args:
        response: HTTP-ответ с Delete-Cookie.
    """
    clear_anon_cookie(response)
