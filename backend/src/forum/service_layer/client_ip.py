"""Извлечение IP клиента из HTTP-запроса."""

import ipaddress
import time

import httpx
from fastapi import Request

from forum.config import configuration
from general.logger import logger


_LOOKUP_TIMEOUT = 2.0
_EGRESS_TTL_SECONDS = 300.0
_IP_API_SELF_URL = 'http://ip-api.com/json/'

# (monotonic_deadline, ip_or_none)
_egress_cache: tuple[float, str | None] | None = None


def is_public_ip(ip: str) -> bool:
    """
    Проверяет, что IP глобальный (доступен из интернета).

    Private (10/8, 172.16/12, 192.168/16), loopback
    (127.0.0.1) и невалидные строки считаются непубличными.

    Args:
        ip: строка IPv4/IPv6.

    Returns:
        True, если адрес публичный; иначе False.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return bool(addr.is_global)


def extract_client_ip(request: Request) -> str | None:
    """
    Достаёт «сырой» IP из заголовков прокси или peer.

    Не подменяет private IP публичным — только читает
    то, что пришло в запросе. Порядок приоритета:
    1) X-Forwarded-For (первый адрес в списке),
    2) X-Real-IP,
    3) request.client.host (TCP peer).

    Args:
        request: входящий HTTP-запрос.

    Returns:
        Строка IP или None, если определить нельзя.
    """
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        first = forwarded.split(',')[0].strip()
        if first:
            return first
    real_ip = request.headers.get('x-real-ip')
    if real_ip and real_ip.strip():
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return None


async def _fetch_egress_public_ip() -> str | None:
    """
    Узнаёт публичный IP исходящего трафика API-контейнера.

    Нужен локально: Docker отдаёт peer 172.x, а geo
    работает только с публичным адресом. Результат
    кэшируется ~5 минут, чтобы не дергать ip-api
    на каждый запрос.

    Returns:
        Публичный IP хоста или None при ошибке сети.
    """
    global _egress_cache
    now = time.monotonic()
    if _egress_cache is not None:
        deadline, cached = _egress_cache
        if now < deadline:
            return cached

    try:
        async with httpx.AsyncClient(
            timeout=_LOOKUP_TIMEOUT,
        ) as client:
            response = await client.get(
                _IP_API_SELF_URL,
                params={'fields': 'status,query'},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning(
            'Egress public IP lookup failed: %s',
            exc,
        )
        _egress_cache = (now + _EGRESS_TTL_SECONDS, None)
        return None

    if data.get('status') != 'success':
        _egress_cache = (now + _EGRESS_TTL_SECONDS, None)
        return None
    query = data.get('query')
    if not query or not is_public_ip(str(query)):
        _egress_cache = (now + _EGRESS_TTL_SECONDS, None)
        return None
    public_ip = str(query).strip()
    _egress_cache = (now + _EGRESS_TTL_SECONDS, public_ip)
    return public_ip


async def resolve_client_ip(
    request: Request,
) -> str | None:
    """
    IP клиента для presence/geo.

    При private/loopback (типичный Docker gateway
    172.x) в DEV подставляет публичный egress IP
    хоста, иначе geo и last_ip локально бесполезны.

    Args:
        request: входящий HTTP-запрос.

    Returns:
        Публичный или исходный IP, либо None.
    """
    ip = extract_client_ip(request)
    if ip and is_public_ip(ip):
        return ip
    if not configuration.visitors.use_egress_ip_when_private:
        return ip
    egress = await _fetch_egress_public_ip()
    return egress or ip
