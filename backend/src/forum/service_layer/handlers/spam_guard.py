"""Проверки антиспама для тем и сообщений."""

from datetime import timedelta
import uuid

from forum.config import configuration
from forum.domain.exceptions import RateLimitExceededError
from forum.service_layer import unit_of_work
from forum.service_layer.timeutils import (
    moscow_today_start_utc,
    utc_now_naive,
)


def _format_window_minutes(seconds: int) -> str:
    minutes = seconds // 60
    if seconds % 60 == 0 and minutes > 0:
        if minutes == 1:
            return '1 минуту'
        if 2 <= minutes <= 4:
            return f'{minutes} минуты'
        return f'{minutes} минут'
    return f'{seconds} сек.'


async def check_message_interval(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Проверяет интервал между сообщениями одного автора.

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора сообщения.

    Raises:
        RateLimitExceededError: если интервал ещё не истёк.
    """
    interval = configuration.discussions.message_min_interval_seconds
    last_at = (
        await uow.post_repository.get_last_created_at_by_author(
            author_id,
        )
    )
    if last_at is None:
        return

    elapsed = (utc_now_naive() - last_at).total_seconds()
    if elapsed < interval:
        raise RateLimitExceededError(
            'Слишком частая отправка. Новое сообщение '
            f'можно отправить не чаще, чем раз в '
            f'{interval} секунд.',
        )


async def check_posts_hourly_limit(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Проверяет почасовой лимит сообщений автора.

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора сообщения.

    Raises:
        RateLimitExceededError: если лимит за час исчерпан.
    """
    limit = configuration.discussions.posts_per_hour_limit
    since = utc_now_naive() - timedelta(hours=1)
    count = await uow.post_repository.count_by_author_since(
        author_id,
        since,
    )
    if count >= limit:
        raise RateLimitExceededError(
            'Достигнут лимит: не более '
            f'{limit} сообщений в час.',
        )


async def check_topics_window_limit(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Проверяет лимит новых тем в скользящем окне.

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора темы.

    Raises:
        RateLimitExceededError: если лимит окна исчерпан.
    """
    cfg = configuration.discussions
    limit = cfg.topics_per_window_limit
    window = cfg.topics_window_seconds
    since = utc_now_naive() - timedelta(seconds=window)
    count = await uow.topic_repository.count_by_author_since(
        author_id,
        since,
    )
    if count >= limit:
        period = _format_window_minutes(window)
        raise RateLimitExceededError(
            'Достигнут лимит: не более '
            f'{limit} новых тем за {period}.',
        )


async def check_topics_daily_limit(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Проверяет суточный лимит новых тем (по Москве).

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора темы.

    Raises:
        RateLimitExceededError: если суточный лимит исчерпан.
    """
    limit = configuration.discussions.topics_per_day_limit
    since = moscow_today_start_utc()
    count = await uow.topic_repository.count_by_author_since(
        author_id,
        since,
    )
    if count >= limit:
        raise RateLimitExceededError(
            'Достигнут суточный лимит: не более '
            f'{limit} новых тем в день.',
        )


async def check_message_limits(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Все проверки перед созданием сообщения.

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора сообщения.

    Raises:
        RateLimitExceededError: если сработал любой лимит.
    """
    await check_message_interval(uow, author_id)
    await check_posts_hourly_limit(uow, author_id)


async def check_topic_limits(
    uow: unit_of_work.AbstractUnitOfWork,
    author_id: uuid.UUID,
) -> None:
    """
    Все проверки перед созданием темы.

    Включает лимиты тем и те же лимиты сообщений,
    т.к. тема создаёт первое сообщение.

    Args:
        uow: unit of work с репозиториями.
        author_id: uid автора темы.

    Raises:
        RateLimitExceededError: если сработал любой лимит.
    """
    await check_topics_window_limit(uow, author_id)
    await check_topics_daily_limit(uow, author_id)
    await check_message_limits(uow, author_id)


async def check_support_ticket_daily_limit(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    user_uid: uuid.UUID | None,
    email: str,
    client_ip: str | None,
) -> None:
    """
    Проверяет суточный лимит обращений в техподдержку (МСК).

    Для авторизованных считает по user_uid; для гостей —
    по email и при наличии — по IP.

    Args:
        uow: unit of work с репозиториями.
        user_uid: uid пользователя или None для гостя.
        email: email из формы обращения.
        client_ip: IP клиента или None.

    Raises:
        RateLimitExceededError: если суточный лимит исчерпан.
    """
    limit = configuration.support.tickets_per_day_limit
    since = moscow_today_start_utc()
    repo = uow.support_ticket_repository

    if user_uid is not None:
        count = await repo.count_by_user_since(user_uid, since)
        if count >= limit:
            raise RateLimitExceededError(
                'Достигнут лимит: не более '
                f'{limit} обращений в техподдержку '
                'в сутки.',
            )
        return

    email_count = await repo.count_by_email_since(
        email,
        since,
    )
    if email_count >= limit:
        raise RateLimitExceededError(
            'Достигнут лимит: не более '
            f'{limit} обращений в техподдержку '
            'в сутки с этого email.',
        )

    if client_ip:
        ip_count = await repo.count_by_ip_since(
            client_ip,
            since,
        )
        if ip_count >= limit:
            raise RateLimitExceededError(
                'Достигнут лимит: не более '
                f'{limit} обращений в техподдержку '
                'в сутки с вашего IP.',
            )
