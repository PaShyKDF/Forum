from forum.domain.models import User
from forum.interfaces.admin.views.base import BaseModelView


class UserAdmin(BaseModelView, model=User):
    """Пользователи форума."""

    column_list = [
        'uid',
        'username',
        'display_name',
        'email',
        'is_guest',
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
        'is_active',
        'last_ip',
        'last_country',
        'last_city',
        'last_ip_at',
        'last_seen_at',
        'created_at',
    ]
    can_delete = False
    category = 'Пользователи'
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
        'registered_at': 'Зарегистрирован',
        'is_active': 'Активен',
        'topics': 'Темы',
        'posts': 'Сообщения',
        'created_at': 'Создан',
        'updated_at': 'Обновлён',
    }
    name = 'Пользователь'
    name_plural = 'Пользователи'
