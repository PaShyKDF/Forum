"""Тесты извлечения и resolve клиентского IP."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forum.service_layer import client_ip as client_ip_mod
from forum.service_layer.client_ip import (
    extract_client_ip,
    is_public_ip,
    resolve_client_ip,
)


def _request(
    *,
    forwarded: str | None = None,
    real_ip: str | None = None,
    peer: str | None = '172.20.0.1',
):
    headers = {}
    if forwarded is not None:
        headers['x-forwarded-for'] = forwarded
    if real_ip is not None:
        headers['x-real-ip'] = real_ip
    request = MagicMock()
    request.headers = headers
    if peer is None:
        request.client = None
    else:
        request.client = SimpleNamespace(host=peer)
    return request


def test_is_public_ip():
    assert is_public_ip('8.8.8.8') is True
    assert is_public_ip('172.20.0.1') is False
    assert is_public_ip('127.0.0.1') is False
    assert is_public_ip('not-an-ip') is False


def test_extract_prefers_forwarded_for():
    request = _request(
        forwarded='203.0.113.10, 172.20.0.1',
        peer='172.20.0.1',
    )
    assert extract_client_ip(request) == '203.0.113.10'


def test_extract_falls_back_to_peer():
    request = _request(peer='172.20.0.1')
    assert extract_client_ip(request) == '172.20.0.1'


@pytest.mark.asyncio
async def test_resolve_keeps_public_ip():
    request = _request(forwarded='203.0.113.10')
    with patch.object(
        client_ip_mod.configuration.visitors,
        'use_egress_ip_when_private',
        True,
    ):
        result = await resolve_client_ip(request)
    assert result == '203.0.113.10'


@pytest.mark.asyncio
async def test_resolve_uses_egress_for_docker_ip():
    request = _request(peer='172.20.0.1')
    client_ip_mod._egress_cache = None
    with (
        patch.object(
            client_ip_mod.configuration.visitors,
            'use_egress_ip_when_private',
            True,
        ),
        patch.object(
            client_ip_mod,
            '_fetch_egress_public_ip',
            new_callable=AsyncMock,
            return_value='198.51.100.20',
        ),
    ):
        result = await resolve_client_ip(request)
    assert result == '198.51.100.20'


@pytest.mark.asyncio
async def test_resolve_keeps_private_when_disabled():
    request = _request(peer='172.20.0.1')
    with (
        patch.object(
            client_ip_mod.configuration.visitors,
            'use_egress_ip_when_private',
            False,
        ),
        patch.object(
            client_ip_mod,
            '_fetch_egress_public_ip',
            new_callable=AsyncMock,
        ) as fetch,
    ):
        result = await resolve_client_ip(request)
    assert result == '172.20.0.1'
    fetch.assert_not_called()
