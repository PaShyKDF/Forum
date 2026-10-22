from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from forum.config import configuration
from forum.service_layer.keycloak_client import KeycloakClient


# state в OAuth-callback: вход шёл из админки
ADMIN_OAUTH_STATE = 'admin'


class KeycloakAdminAuth(AuthenticationBackend):
    """Авторизация SQLAdmin через Keycloak (роль admin)."""

    async def login(self, request: Request) -> bool:
        """POST не используется — вход через Keycloak redirect."""
        return False

    async def logout(self, request: Request) -> bool:
        """
        Очищает session SQLAdmin при выходе.

        Args:
            request: запрос logout админки.

        Returns:
            True после очистки session.
        """
        request.session.clear()
        return True

    async def authenticate(
        self,
        request: Request,
    ) -> Response | bool:
        """
        Проверяет cookie access_token и роль admin.

        Без валидного токена — False (редирект на login).
        Без нужной роли — 302 на login?error=forbidden.
        Иначе помечает session и возвращает True.

        Args:
            request: запрос к защищённой странице админки.

        Returns:
            True, False или RedirectResponse при запрете.
        """
        token = request.cookies.get('access_token')
        if not token or KeycloakClient.is_token_expired(
            token,
        ):
            return False

        required_role = configuration.admin.required_role
        if not KeycloakClient.has_role(token, required_role):
            return RedirectResponse(
                url=(
                    f'{request.url_for("admin:login")}'
                    f'?error=forbidden'
                ),
                status_code=302,
            )

        request.session['admin_authenticated'] = True
        return True


authentication_backend = KeycloakAdminAuth(
    secret_key=configuration.admin.auth_secret_key,
)
