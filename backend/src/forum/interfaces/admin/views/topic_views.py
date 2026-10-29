from forum.domain.models import TopicView
from forum.interfaces.admin.views.base import (
    BaseModelView,
    format_moscow_datetime,
    format_moscow_datetime_detail,
)


class TopicViewAdmin(BaseModelView, model=TopicView):
    """История ежедневных просмотров тем."""

    column_list = [
        'id',
        'topic',
        'user',
        'anon_id',
        'view_date',
        'viewed_at',
    ]
    column_searchable_list = ['anon_id', 'viewer_key']
    column_sortable_list = [
        'id',
        'view_date',
        'viewed_at',
    ]
    column_formatters = {
        **BaseModelView.column_formatters,
        'viewed_at': format_moscow_datetime,
    }
    column_formatters_detail = {
        **BaseModelView.column_formatters_detail,
        'viewed_at': format_moscow_datetime_detail,
    }
    column_labels = {
        'id': 'ID',
        'topic': 'Тема',
        'topic_id': 'ID темы',
        'viewer_key': 'Ключ зрителя',
        'user': 'Пользователь',
        'user_id': 'ID пользователя',
        'anon_id': 'Anon ID',
        'view_date': 'Дата (МСК)',
        'viewed_at': 'Время',
    }
    name = 'Просмотр темы'
    name_plural = 'Просмотры тем'
    category = 'Форум'
    can_create = False
    can_edit = False
    can_delete = False
