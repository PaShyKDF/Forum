"""HTTP-клиент Keycloak: OIDC token/userinfo и хелперы JWT."""

import base64
import json
import logging
import time
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from forum.config import configuration


logger = logging.getLogger(__name__)

# Совпадает с ADMIN_OAUTH_STATE в interfaces.admin.auth
_ADMIN_STATE = 'admin'


class KeycloakClient:
    """
    Обёртка над OIDC-эндпоинтами Keycloak.

    Использует переданный httpx.AsyncClient (обычно общий
    на lifespan приложения). Token/userinfo идут на
    internal_base_url; auth/logout URL — на public_base_url.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ):
        """
        Инициализирует клиент Keycloak.

        Args:
            client: async HTTP-клиент; если None — создаётся
                новый (для тестов). В проде передавайте
                shared-клиент из lifespan.
        """
        self.client = client or httpx.AsyncClient()

    async def get_tokens(
        self,
        code: str,
        *,
        redirect_uri: str | None = None,
    ) -> dict:
        """
        Обменивает authorization code на набор токенов.

        POST на token endpoint с grant_type=authorization_code.
        redirect_uri должен совпадать с тем, что ушёл в /auth;
        иначе Keycloak вернёт invalid_grant. Code одноразовый.

        Args:
            code: одноразовый code из query callback.
            redirect_uri: URI callback; по умолчанию forum
                redirect_uri из конфига.

        Returns:
            JSON Keycloak: access_token, refresh_token,
            id_token, expires_in и др.

        Raises:
            HTTPException: 500 при сетевой ошибке, 401 при
                отказе Keycloak.
        """
        uri = (
            redirect_uri
            or configuration.keycloak.redirect_uri
        )
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': uri,
            'client_id': configuration.keycloak.CLIENT_ID,
            'client_secret': (
                configuration.keycloak.CLIENT_SECRET
            ),
        }
        headers = {
            'Content-Type': (
                'application/x-www-form-urlencoded'
            ),
        }
        token_url = configuration.keycloak.token_url

        try:
            response = await self.client.post(
                token_url,
                data=data,
                headers=headers,
            )
        except httpx.RequestError as e:
            logger.error(
                'Token exchange connection failed url=%s: %s',
                token_url,
                e,
            )
            raise HTTPException(
                status_code=500,
                detail=f'Token exchange failed: {str(e)}',
            ) from e

        if response.status_code != 200:
            logger.error(
                'Token exchange rejected url=%s '
                'redirect_uri=%s status=%s body=%s',
                token_url,
                uri,
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=401,
                detail=(
                    f'Token request failed: {response.text}'
                ),
            )

        return response.json()

    async def refresh_tokens(self, refresh_token: str) -> dict:
        """
        Обменивает refresh_token на новый набор токенов.

        POST на token endpoint с grant_type=refresh_token.

        Args:
            refresh_token: refresh JWT из cookie.

        Returns:
            JSON Keycloak: access_token, refresh_token,
            id_token (может отсутствовать), expires_in.

        Raises:
            HTTPException: 500 при сетевой ошибке, 401 при
                отказе Keycloak.
        """
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': configuration.keycloak.CLIENT_ID,
            'client_secret': (
                configuration.keycloak.CLIENT_SECRET
            ),
        }
        headers = {
            'Content-Type': (
                'application/x-www-form-urlencoded'
            ),
        }
        token_url = configuration.keycloak.token_url

        try:
            response = await self.client.post(
                token_url,
                data=data,
                headers=headers,
            )
        except httpx.RequestError as e:
            logger.error(
                'Token refresh connection failed url=%s: %s',
                token_url,
                e,
            )
            raise HTTPException(
                status_code=500,
                detail=f'Token refresh failed: {str(e)}',
            ) from e

        if response.status_code != 200:
            logger.error(
                'Token refresh rejected url=%s '
                'status=%s body=%s',
                token_url,
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=401,
                detail=(
                    f'Token refresh failed: {response.text}'
                ),
            )

        return response.json()

    async def get_user_info(self, token: str) -> dict:
        """
        Профиль пользователя по access_token.

        Сначала GET userinfo; при ошибке (часто из-за
        разного iss на dual-host) — claims из JWT payload
        без проверки подписи.

        Args:
            token: Bearer access_token.

        Returns:
            Словарь userinfo/claims (ожидается ключ sub).

        Raises:
            HTTPException: 401, если JWT битый или нет sub.
        """
        headers = {'Authorization': f'Bearer {token}'}
        try:
            response = await self.client.get(
                configuration.keycloak.userinfo_url,
                headers=headers,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                'userinfo %s: %s — claims из JWT',
                response.status_code,
                response.text[:200],
            )
        except httpx.RequestError as e:
            logger.warning(
                'userinfo недоступен (%s) — claims из JWT',
                e,
            )

        try:
            payload = self.decode_token_payload(token)
        except (ValueError, json.JSONDecodeError) as e:
            raise HTTPException(
                status_code=401,
                detail=f'Invalid access token: {e}',
            ) from e

        if not payload.get('sub'):
            raise HTTPException(
                status_code=401,
                detail='Invalid access token: no sub claim',
            )
        return payload

    @classmethod
    def user_info_from_id_token(cls, id_token: str) -> dict:
        """
        Достаёт claims профиля из OIDC id_token.

        Args:
            id_token: JWT id_token.

        Returns:
            Payload JWT как dict.
        """
        return cls.decode_token_payload(id_token)

    @staticmethod
    def resolve_redirect_uri(
        state: str | None = None,
    ) -> str:
        """
        Выбирает redirect_uri по OAuth state.

        state=admin → callback на порту API (SQLAdmin);
        иначе → callback через frontend nginx (SPA cookies).

        Args:
            state: значение state из /auth или callback.

        Returns:
            Абсолютный URL callback.
        """
        if state == _ADMIN_STATE:
            return configuration.keycloak.admin_redirect_uri
        return configuration.keycloak.redirect_uri

    @staticmethod
    def build_auth_url(
        *,
        state: str | None = None,
        redirect_uri: str | None = None,
        kc_action: str | None = None,
    ) -> str:
        """
        Собирает URL authorization endpoint Keycloak.

        Args:
            state: произвольный state (для admin — 'admin').
            redirect_uri: явный callback; если None —
                resolve_redirect_uri(state).
            kc_action: опционально, напр. UPDATE_PASSWORD.

        Returns:
            Полный URL с query (client_id, code, scope…).
        """
        uri = redirect_uri or (
            KeycloakClient.resolve_redirect_uri(state)
        )
        params = {
            'client_id': configuration.keycloak.CLIENT_ID,
            'response_type': 'code',
            'scope': 'openid profile email',
            'redirect_uri': uri,
            'ui_locales': 'ru',
        }
        if state:
            params['state'] = state
        if kc_action:
            params['kc_action'] = kc_action
        return (
            f'{configuration.keycloak.auth_url}'
            f'?{urlencode(params)}'
        )

    @staticmethod
    def build_logout_url(
        *,
        post_logout_redirect_uri: str,
        id_token: str | None = None,
    ) -> str:
        """
        Собирает URL end-session (logout) Keycloak.

        Args:
            post_logout_redirect_uri: куда вернуть браузер
                после выхода (должен быть в Valid post
                logout redirect URIs клиента).
            id_token: опциональный id_token_hint.

        Returns:
            Полный URL logout с query.
        """
        params = {
            'client_id': configuration.keycloak.CLIENT_ID,
            'post_logout_redirect_uri': (
                post_logout_redirect_uri
            ),
            'ui_locales': 'ru',
        }
        if id_token:
            params['id_token_hint'] = id_token
        return (
            f'{configuration.keycloak.logout_url}'
            f'?{urlencode(params)}'
        )

    @staticmethod
    def decode_token_payload(token: str) -> dict:
        """
        Декодирует payload JWT без проверки подписи.

        Args:
            token: строка JWT (header.payload.signature).

        Returns:
            Объект payload.

        Raises:
            ValueError: некорректный формат или не-object JSON.
        """
        parts = token.split('.')
        if len(parts) < 2:
            raise ValueError('Некорректный JWT')

        payload = parts[1]
        padding = '=' * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('Payload JWT не объект')
        return data

    @classmethod
    def is_token_expired(cls, token: str) -> bool:
        """
        Проверяет claim exp access_token.

        Args:
            token: JWT access_token.

        Returns:
            True, если токен битый, без exp или уже истёк.
        """
        try:
            payload = cls.decode_token_payload(token)
        except (ValueError, json.JSONDecodeError):
            return True

        exp = payload.get('exp')
        if exp is None:
            return True
        return int(exp) <= int(time.time())

    @classmethod
    def extract_roles(cls, token: str) -> set[str]:
        """
        Собирает роли из realm_access и resource_access.

        Args:
            token: JWT access_token.

        Returns:
            Множество имён ролей (строки).
        """
        payload = cls.decode_token_payload(token)
        roles: set[str] = set()

        realm_roles = payload.get('realm_access', {}).get(
            'roles',
            [],
        )
        if isinstance(realm_roles, list):
            roles.update(str(role) for role in realm_roles)

        client_id = configuration.keycloak.CLIENT_ID
        resource_access = payload.get('resource_access', {})
        if isinstance(resource_access, dict):
            client_roles = resource_access.get(
                client_id,
                {},
            ).get('roles', [])
            if isinstance(client_roles, list):
                roles.update(
                    str(role) for role in client_roles
                )

        flat_roles = payload.get('roles', [])
        if isinstance(flat_roles, list):
            roles.update(str(role) for role in flat_roles)

        return roles

    @classmethod
    def has_role(cls, token: str, role: str) -> bool:
        """
        Есть ли у access_token указанная роль.

        Args:
            token: JWT access_token.
            role: имя роли (realm или client).

        Returns:
            True при наличии роли; False при битом токене.
        """
        try:
            return role in cls.extract_roles(token)
        except (ValueError, json.JSONDecodeError):
            return False
