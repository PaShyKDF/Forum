"""Геолокация по IP через бесплатный HTTP lookup."""

import httpx

from forum.service_layer.client_ip import is_public_ip
from general.logger import logger


_LOOKUP_TIMEOUT = 2.0
_IP_API_URL = 'http://ip-api.com/json/{ip}'


async def lookup_geo(
    ip: str | None,
) -> tuple[str | None, str | None] | None:
    """
    Страна и город по IP через ip-api.com.

    Private/loopback не резолвит. Ошибки сети только в лог.

    Args:
        ip: строка IPv4/IPv6 или None.

    Returns:
        (country, city) или None при ошибке/непубличном IP.
    """
    if not ip or not is_public_ip(ip):
        return None
    url = _IP_API_URL.format(ip=ip.strip())
    try:
        async with httpx.AsyncClient(
            timeout=_LOOKUP_TIMEOUT,
        ) as client:
            response = await client.get(
                url,
                params={'fields': 'status,country,city'},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning(
            'GeoIP lookup failed for %s: %s',
            ip,
            exc,
        )
        return None

    if data.get('status') != 'success':
        return None
    country = data.get('country') or None
    city = data.get('city') or None
    if not country and not city:
        return None
    return (
        str(country)[:64] if country else None,
        str(city)[:128] if city else None,
    )
