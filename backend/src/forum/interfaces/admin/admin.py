"""SQLAdmin: русские кнопки и вход через Keycloak."""

from typing import Any

from sqladmin import Admin
from sqladmin.helpers import get_object_identifier
from sqladmin.models import ModelView
from starlette.datastructures import URL, FormData
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from forum.config import configuration
from forum.interfaces.admin.auth import ADMIN_OAUTH_STATE
from forum.service_layer.auth_cookies import clear_auth_cookies
from forum.service_layer.keycloak_client import KeycloakClient


class RuAdmin(Admin):
    """SQLAdmin с русскими кнопками и Keycloak-логином."""

    def get_save_redirect_url(
        self,
        request: Request,
        form: FormData,
        model_view: ModelView,
        obj: Any,
    ) -> str | URL:
        """
        URL после сохранения с учётом русских кнопок.

        Распознаёт «Сохранить», «Сохранить и продолжить
        редактирование» и «Сохранить как новый».

        Args:
            request: запрос формы create/edit.
            form: данные формы (кнопка save).
            model_view: текущая ModelView.
            obj: сохранённый объект или None.

        Returns:
            URL списка, редактирования или создания.
        """
        identity = request.path_params['identity']

        if obj is None:
            return request.url_for('admin:list', identity=identity)

        identifier = get_object_identifier(obj)

        if form.get('save') == 'Сохранить':
            return request.url_for('admin:list', identity=identity)
        if form.get('save') == (
            'Сохранить и продолжить редактирование'
        ) or (
            form.get('save') == 'Сохранить как новый'
            and model_view.save_as_continue
        ):
            return request.url_for(
                'admin:edit',
                identity=identity,
                pk=identifier,
            )
        return request.url_for('admin:create', identity=identity)

    async def _forbidden_response(
        self,
        request: Request,
        required_role: str,
    ) -> Response:
        """Страница логина с текстом про отсутствие роли."""
        return await self.templates.TemplateResponse(
            request,
            'sqladmin/login.html',
            {
                'error': (
                    f'Доступ запрещён. Нужна роль '
                    f'«{required_role}» в Keycloak.'
                ),
            },
            status_code=403,
        )

    async def login(self, request: Request) -> Response:
        """
        Вход в SQLAdmin через Keycloak OIDC.

        Если в query error=forbidden — показать отказ.
        Если есть валидный access_token с ролью admin —
        сразу в /admin/. Иначе GET редиректит на Keycloak
        с admin redirect_uri и state=admin.

        Args:
            request: запрос страницы /admin/login.

        Returns:
            302 на Keycloak/admin или 403 login.html.
        """
        assert self.authentication_backend is not None

        required_role = configuration.admin.required_role
        if request.query_params.get('error') == 'forbidden':
            return await self._forbidden_response(
                request,
                required_role,
            )

        token = request.cookies.get('access_token')
        if (
            token
            and not KeycloakClient.is_token_expired(token)
        ):
            if KeycloakClient.has_role(token, required_role):
                return RedirectResponse(
                    request.url_for('admin:index'),
                    status_code=302,
                )
            return await self._forbidden_response(
                request,
                required_role,
            )

        if request.method == 'GET':
            return RedirectResponse(
                KeycloakClient.build_auth_url(
                    state=ADMIN_OAUTH_STATE,
                ),
                status_code=302,
            )

        return RedirectResponse(
            request.url_for('admin:login'),
            status_code=302,
        )

    async def logout(self, request: Request) -> Response:
        """
        Выход из SQLAdmin: session + cookies + Keycloak SSO.

        Args:
            request: запрос logout админки.

        Returns:
            302 на Keycloak logout (post_logout → BASE_URL).
        """
        assert self.authentication_backend is not None
        await self.authentication_backend.logout(request)

        id_token = request.cookies.get('id_token')
        logout_url = KeycloakClient.build_logout_url(
            post_logout_redirect_uri=(
                configuration.keycloak.BASE_URL
            ),
            id_token=id_token,
        )
        response = RedirectResponse(
            logout_url,
            status_code=302,
        )
        clear_auth_cookies(response)
        return response
