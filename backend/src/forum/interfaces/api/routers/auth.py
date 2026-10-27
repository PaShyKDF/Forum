"""OIDC auth: старт входа, callback, сессия, logout."""

import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import RedirectResponse

from forum.config import configuration
from forum.domain.schemas.auth import AuthSessionResponse
from forum.interfaces.admin.auth import ADMIN_OAUTH_STATE
from forum.service_layer.auth_cookies import (
    POST_LOGIN_NEXT_COOKIE,
    build_post_login_url,
    clear_auth_cookies,
    clear_post_login_next_cookie,
    refresh_session_if_needed,
    sanitize_post_login_next,
    set_auth_cookies,
    set_post_login_next_cookie,
)
from forum.service_layer.auth_dep import (
    get_keycloak_client,
    token_is_admin,
)
from forum.service_layer.client_ip import resolve_client_ip
from forum.service_layer.handlers.auth import (
    ensure_user_command_from_keycloak,
)
from forum.service_layer.handlers.visitors import (
    finalize_guest_cookie_after_login,
)
from forum.service_layer.keycloak_client import KeycloakClient
from forum.service_layer.messagebus import (
    MessageBus,
    get_message_bus,
)
from forum.service_layer.visitor_cookies import (
    clear_anon_cookie,
    read_anon_id,
)


router = APIRouter(
    tags=['auth'],
)

logger = logging.getLogger(__name__)


def _require_token_trio(
    token_data: dict,
) -> tuple[str, str, str]:
    """
    Достаёт access/refresh/id из ответа token endpoint.

    Args:
        token_data: JSON Keycloak после обмена code.

    Returns:
        Кортеж (access_token, refresh_token, id_token).

    Raises:
        HTTPException: 401, если какого-то токена нет.
    """
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    id_token = token_data.get('id_token')
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail='Токен доступа не найден',
        )
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail='Refresh token не найден',
        )
    if not id_token:
        raise HTTPException(
            status_code=401,
            detail='ID token не найден',
        )
    return access_token, refresh_token, id_token


def _redirect_after_login(
    *,
    state: str | None,
    has_admin: bool,
    next_path: str | None = None,
) -> RedirectResponse:
    """
    Куда отправить браузер после успешного обмена code.

    Args:
        state: OAuth state (admin → SQLAdmin).
        has_admin: есть ли у пользователя роль admin.
        next_path: безопасный SPA-путь возврата (#/…).

    Returns:
        RedirectResponse без cookies (их ставит caller).
    """
    is_admin_login = state == ADMIN_OAUTH_STATE
    if is_admin_login and not has_admin:
        return RedirectResponse(
            url='/admin/login?error=forbidden',
            status_code=302,
        )
    if is_admin_login:
        return RedirectResponse(
            url='/admin/',
            status_code=302,
        )
    return RedirectResponse(
        url=build_post_login_url(next_path),
        status_code=302,
    )


async def _persist_user_from_tokens(
    *,
    keycloak: KeycloakClient,
    access_token: str,
    id_token: str | None,
    message_bus: MessageBus,
    anon_id: str | None = None,
    client_ip: str | None = None,
):
    """
    Upsert пользователя в БД по claims Keycloak.

    Предпочитает claims id_token (без лишнего HTTP);
    иначе userinfo по access_token. Затем EnsureUserCommand
    через MessageBus. anon_id — cookie гостя для merge.

    Args:
        keycloak: клиент Keycloak (userinfo при нужде).
        access_token: JWT доступа.
        id_token: OIDC id_token или None.
        message_bus: Depends MessageBus.
        anon_id: cookie гостя для merge или None.
        client_ip: IP клиента для last_ip/geo.

    Returns:
        UserResponse с флагом is_admin по роли токена.

    Raises:
        HTTPException: 401 при невалидных claims.
    """
    try:
        if id_token:
            user_info = (
                KeycloakClient.user_info_from_id_token(
                    id_token,
                )
            )
        else:
            user_info = await keycloak.get_user_info(
                access_token,
            )
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=401,
            detail=f'Invalid token claims: {e}',
        ) from e

    command = ensure_user_command_from_keycloak(
        user_info,
        anon_id=anon_id,
        client_ip=client_ip,
    )
    user = await message_bus.handle(command)
    user.is_admin = token_is_admin(access_token)
    return user


@router.get(
    '/auth/start',
    summary='Старт OIDC-входа (редирект в Keycloak)',
    include_in_schema=False,
)
async def auth_start(
    next: str | None = None,
) -> RedirectResponse:
    """
    Начинает authorization code flow для форума.

    Редиректит браузер на Keycloak /auth с forum
    redirect_uri (через nginx), чтобы после callback
    cookies оказались на origin SPA.

    Query next — SPA-путь возврата (#/topic/1), сохраняется
    в cookie на время логина.

    Returns:
        302 на Keycloak authorization URL.
    """
    response = RedirectResponse(
        url=KeycloakClient.build_auth_url(),
        status_code=302,
    )
    safe_next = sanitize_post_login_next(next)
    if safe_next:
        set_post_login_next_cookie(response, safe_next)
    return response


@router.get(
    '/auth/me',
    response_model=AuthSessionResponse,
    summary='Текущий пользователь',
)
async def auth_me(
    request: Request,
    response: Response,
    keycloak: KeycloakClient = Depends(get_keycloak_client),
    message_bus: MessageBus = Depends(get_message_bus),
) -> AuthSessionResponse:
    """
    Возвращает профиль пользователя по cookie-сессии.

    Читает access_token (и id_token) из cookies; при
    истечении access обновляет токены через refresh,
    upsert'ит пользователя в БД и отдаёт UserResponse.

    Args:
        request: HTTP-запрос с cookies.
        response: ответ для обновления auth-cookies.
        keycloak: Depends KeycloakClient.
        message_bus: Depends MessageBus.

    Returns:
        AuthSessionResponse с user и message.

    Raises:
        HTTPException: 401 без токена или при истёкшей сессии.
    """
    access_token = await refresh_session_if_needed(
        request,
        response,
        keycloak,
    )
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail='Не авторизован',
        )
    id_token = request.cookies.get('id_token')
    if id_token and KeycloakClient.is_token_expired(
        id_token,
    ):
        # После refresh request.cookies ещё старые;
        # берём профиль по новому access_token.
        id_token = None

    user = await _persist_user_from_tokens(
        keycloak=keycloak,
        access_token=access_token,
        id_token=id_token,
        message_bus=message_bus,
        anon_id=read_anon_id(request),
        client_ip=await resolve_client_ip(request),
    )
    finalize_guest_cookie_after_login(response)
    return AuthSessionResponse(
        user=user,
        message='OK',
    )


@router.get('/login/callback', include_in_schema=False)
async def login_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    keycloak: KeycloakClient = Depends(get_keycloak_client),
    message_bus: MessageBus = Depends(get_message_bus),
) -> RedirectResponse:
    """
    OIDC callback после авторизации в Keycloak.

    Обменивает code на токены (redirect_uri зависит от
    state), сохраняет пользователя, ставит cookies и
    редиректит: forum → страница из cookie next или
    frontend/#/, admin → /admin/ (или forbidden без роли).

    Args:
        request: запрос (cookie post_login_next).
        code: authorization code от Keycloak.
        state: 'admin' для SQLAdmin, иначе форум.
        error: код ошибки Keycloak (если отказ).
        error_description: текст ошибки Keycloak.
        keycloak: Depends KeycloakClient.
        message_bus: Depends MessageBus.

    Returns:
        302 с Set-Cookie на целевую страницу.

    Raises:
        HTTPException: 401 при ошибке/отсутствии code.
    """
    if error:
        logger.error(
            'Keycloak error: %s, description: %s',
            error,
            error_description,
        )
        if state == ADMIN_OAUTH_STATE:
            return RedirectResponse(
                url='/admin/login?error=forbidden',
                status_code=302,
            )
        next_path = sanitize_post_login_next(
            request.cookies.get(POST_LOGIN_NEXT_COOKIE),
        )
        response = RedirectResponse(
            url=build_post_login_url(next_path or '#/'),
            status_code=302,
        )
        clear_post_login_next_cookie(response)
        return response

    if not code:
        raise HTTPException(
            status_code=401,
            detail='Authorization code is required',
        )
    try:
        redirect_uri = KeycloakClient.resolve_redirect_uri(
            state,
        )
        token_data = await keycloak.get_tokens(
            code,
            redirect_uri=redirect_uri,
        )
        access_token, refresh_token, id_token = (
            _require_token_trio(token_data)
        )

        user = await _persist_user_from_tokens(
            keycloak=keycloak,
            access_token=access_token,
            id_token=id_token,
            message_bus=message_bus,
            anon_id=read_anon_id(request),
            client_ip=await resolve_client_ip(request),
        )

        required_role = configuration.admin.required_role
        has_admin = KeycloakClient.has_role(
            access_token,
            required_role,
        )
        if state == ADMIN_OAUTH_STATE and not has_admin:
            logger.warning(
                'User %s без роли %s пытался войти в admin',
                user.uid,
                required_role,
            )

        next_path = sanitize_post_login_next(
            request.cookies.get(POST_LOGIN_NEXT_COOKIE),
        )
        response = _redirect_after_login(
            state=state,
            has_admin=has_admin,
            next_path=next_path,
        )
        set_auth_cookies(
            response,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            token_data=token_data,
        )
        clear_post_login_next_cookie(response)
        finalize_guest_cookie_after_login(response)
        logger.info('User %s logged in successfully', user.uid)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Ошибка обработки callback логина: %s',
            str(e),
        )
        raise HTTPException(
            status_code=401,
            detail='Ошибка авторизации',
        ) from e


@router.get('/logout', include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    """
    SSO-выход: чистит cookies и уводит на Keycloak logout.

    post_logout_redirect_uri = frontend_url, чтобы после
    end-session пользователь вернулся на сайт.

    Args:
        request: запрос (для чтения id_token cookie).

    Returns:
        302 на Keycloak logout с Delete-Cookie.
    """
    id_token = request.cookies.get('id_token')
    logout_url = KeycloakClient.build_logout_url(
        post_logout_redirect_uri=(
            configuration.keycloak.frontend_url
        ),
        id_token=id_token,
    )
    response = RedirectResponse(url=logout_url)
    clear_auth_cookies(response)
    clear_anon_cookie(response)
    return response
