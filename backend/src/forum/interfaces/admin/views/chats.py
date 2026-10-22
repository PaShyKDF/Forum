from forum.domain.models import DirectChat, DirectMessage
from forum.interfaces.admin.views.base import BaseModelView


class DirectChatAdmin(BaseModelView, model=DirectChat):
    """Личные диалоги."""

    column_list = [
        'id',
        'user_low',
        'user_high',
        'is_active',
        'created_at',
        'updated_at',
    ]
    form_excluded_columns = [
        'messages',
        'created_at',
        'updated_at',
    ]
    column_sortable_list = [
        'id',
        'is_active',
        'created_at',
        'updated_at',
    ]
    column_labels = {
        'id': 'ID',
        'user_low': 'Участник 1',
        'user_high': 'Участник 2',
        'user_low_id': 'ID участника 1',
        'user_high_id': 'ID участника 2',
        'messages': 'Сообщения',
        'is_active': 'Активен',
        'created_at': 'Создан',
        'updated_at': 'Обновлён',
    }
    name = 'Диалог'
    name_plural = 'Личные диалоги'
    category = 'Чаты'
    can_delete = False


class DirectMessageAdmin(BaseModelView, model=DirectMessage):
    """Сообщения личных диалогов."""

    column_list = [
        'id',
        'chat',
        'sender',
        'kind',
        'read_at',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'created_at',
        'updated_at',
    ]
    column_searchable_list = ['body']
    column_sortable_list = [
        'id',
        'kind',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'chat': 'Диалог',
        'chat_id': 'ID диалога',
        'sender': 'Отправитель',
        'sender_id': 'ID отправителя',
        'kind': 'Тип',
        'body': 'Текст',
        'read_at': 'Прочитано',
        'is_active': 'Активно',
        'created_at': 'Создано',
        'updated_at': 'Обновлено',
    }
    name = 'Личное сообщение'
    name_plural = 'Личные сообщения'
    category = 'Чаты'
    can_delete = False
    form_widget_args = {
        'body': {
            'rows': 8,
        },
    }
