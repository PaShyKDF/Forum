from typing import Any
import uuid

from starlette.exceptions import HTTPException
from starlette.requests import Request

from forum.domain.models import User
from forum.interfaces.admin.views.base import BaseModelView
from forum.service_layer.user_deletion import (
    admin_uid_from_request_token,
    anonymize_user,
)


class UserAdmin(BaseModelView, model=User):
    """Пользователи форума."""

    column_list = [
        'uid',
        'username',
        'display_name',
        'email',
        'is_guest',
        'is_deleted',
        'is_active',
        'last_ip',
        'last_country',
        'last_city',
        'last_ip_at',
        'last_seen_at',
        'created_at',
    ]
    form_excluded_columns = [
        'topics',
        'posts',
        'avatar_blob',
        'created_at',
        'updated_at',
    ]
    column_searchable_list = [
        'username',
        'display_name',
        'email',
        'anon_id',
        'last_ip',
    ]
    column_sortable_list = [
        'uid',
        'username',
        'display_name',
        'is_guest',
        'is_deleted',
        'is_active',
        'last_ip',
        'last_country',
        'last_city',
        'last_ip_at',
        'last_seen_at',
        'created_at',
    ]
    category = 'Пользователи'
    delete_warning = (
        'Пользователь будет обезличен '
        '(«Пользователь удален»). Сообщения и темы '
        'останутся. Повторная регистрация с тем же '
        'email или IP будет запрещена.'
    )
    column_labels = {
        'uid': 'UUID',
        'username': 'Логин',
        'email': 'Email',
        'email_verified': 'Email подтверждён',
        'display_name': 'Имя',
        'initials': 'Инициалы',
        'avatar_url': 'Аватар URL',
        'avatar_mime': 'MIME аватара',
        'last_seen_at': 'Был в сети',
        'last_ip': 'Последний IP',
        'last_country': 'Страна',
        'last_city': 'Город',
        'last_ip_at': 'IP обновлён',
        'anon_id': 'Anon ID',
        'is_guest': 'Гость',
        'is_deleted': 'Удалён',
        'registered_at': 'Зарегистрирован',
        'is_active': 'Активен',
        'topics': 'Темы',
        'posts': 'Сообщения',
        'created_at': 'Создан',
        'updated_at': 'Обновлён',
    }
    name = 'Пользователь'
    name_plural = 'Пользователи'

    async def delete_model(
        self,
        request: Request,
        pk: Any,
    ) -> None:
        """
        Обезличивает пользователя вместо hard-delete.

        Args:
            request: DELETE с confirm=1.
            pk: uid пользователя.

        Raises:
            HTTPException: без confirm, self-delete,
                или пользователь не найден.
        """
        if request.query_params.get('confirm') != '1':
            raise HTTPException(
                status_code=400,
                detail=(
                    'Нужно подтвердить удаление '
                    '(чекбокс согласия)'
                ),
            )

        try:
            user_uid = uuid.UUID(str(pk))
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail='Пользователь не найден',
            ) from exc

        admin_uid = admin_uid_from_request_token(
            request.cookies.get('access_token'),
        )
        if admin_uid is not None and admin_uid == user_uid:
            raise HTTPException(
                status_code=400,
                detail='Нельзя удалить самого себя',
            )

        async with self.session_maker() as session:
            user = await session.get(User, user_uid)
            if user is None:
                raise HTTPException(
                    status_code=404,
                    detail='Пользователь не найден',
                )
            if user.is_deleted:
                return
            anonymize_user(user)
            await session.commit()
