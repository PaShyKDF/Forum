"""Хелперы времени: UTC в БД, Москва в UI."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


MSK = ZoneInfo('Europe/Moscow')


def utc_now_naive() -> datetime:
    """
    Текущее UTC-время без tzinfo (как в колонках БД).

    Returns:
        Naive datetime в UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def moscow_today_start_utc() -> datetime:
    """
    Начало текущих суток по Москве в UTC (naive).

    Берёт 00:00 Europe/Moscow и переводит в UTC без
    tzinfo — удобно для суточных лимитов в БД.

    Returns:
        Naive datetime в UTC.
    """
    now_msk = datetime.now(MSK)
    start_msk = datetime.combine(
        now_msk.date(),
        time.min,
        tzinfo=MSK,
    )
    return start_msk.astimezone(timezone.utc).replace(
        tzinfo=None,
    )


def to_moscow(dt: datetime | None) -> datetime | None:
    """
    Переводит naive/aware UTC datetime в Europe/Moscow.

    Args:
        dt: значение из БД (обычно naive UTC) или None.

    Returns:
        aware datetime в MSK или None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK)


def format_moscow_datetime_value(
    dt: datetime | None,
    *,
    fmt: str = '%d.%m.%Y %H:%M:%S',
) -> str:
    """
    Форматирует дату/время в московском часовом поясе.

    Args:
        dt: значение из БД (обычно naive UTC) или None.
        fmt: формат strftime (по умолчанию с секундами).

    Returns:
        Отформатированная строка или '' при None.
    """
    moscow = to_moscow(dt)
    if moscow is None:
        return ''
    return moscow.strftime(fmt)
