from forum.domain.models import TopicNotification
from forum.interfaces.admin.views.base import BaseModelView


class TopicNotificationAdmin(
    BaseModelView,
    model=TopicNotification,
):
    """Уведомления о ответах и цитатах."""

    column_list = [
        'id',
        'recipient',
        'actor',
        'topic',
        'kind',
        'read_at',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'created_at',
        'updated_at',
    ]
    column_sortable_list = [
        'id',
        'kind',
        'read_at',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'recipient': 'Получатель',
        'recipient_id': 'ID получателя',
        'actor': 'Автор действия',
        'actor_id': 'ID автора',
        'topic': 'Тема',
        'topic_id': 'ID темы',
        'post': 'Новое сообщение',
        'post_id': 'ID нового сообщения',
        'source_post': 'Исходное сообщение',
        'source_post_id': 'ID исходного сообщения',
        'kind': 'Тип',
        'read_at': 'Прочитано',
        'is_active': 'Активно',
        'created_at': 'Создано',
        'updated_at': 'Обновлено',
    }
    name = 'Уведомление'
    name_plural = 'Уведомления тем'
    category = 'Уведомления'
    can_create = False
    can_delete = False
