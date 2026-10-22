from forum.domain.models import SupportTicket
from forum.interfaces.admin.views.base import BaseModelView


class SupportTicketAdmin(BaseModelView, model=SupportTicket):
    """Обращения в техническую поддержку."""

    column_list = [
        'id',
        'email',
        'subject',
        'user',
        'status',
        'client_ip',
        'created_at',
    ]
    form_excluded_columns = [
        'created_at',
        'updated_at',
    ]
    column_searchable_list = [
        'email',
        'subject',
        'body',
        'client_ip',
    ]
    column_sortable_list = [
        'id',
        'email',
        'status',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'user': 'Пользователь',
        'user_id': 'ID пользователя',
        'email': 'Email',
        'subject': 'Тема',
        'body': 'Текст',
        'status': 'Статус',
        'client_ip': 'IP клиента',
        'is_active': 'Активно',
        'created_at': 'Создано',
        'updated_at': 'Обновлено',
    }
    name = 'Обращение'
    name_plural = 'Обращения в техподдержку'
    category = 'Поддержка'
    can_create = False
    can_delete = False
    form_widget_args = {
        'body': {
            'rows': 10,
        },
    }
