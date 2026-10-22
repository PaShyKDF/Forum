from forum.domain.models import Post
from forum.interfaces.admin.views.base import BaseModelView


class PostAdmin(BaseModelView, model=Post):
    """Сообщения форума."""

    column_list = [
        'id',
        'topic',
        'author',
        'is_topic_starter',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'replies',
        'created_at',
        'updated_at',
    ]
    column_searchable_list = ['body']
    column_sortable_list = [
        'id',
        'is_topic_starter',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'topic': 'Тема',
        'topic_id': 'ID темы',
        'author': 'Автор',
        'author_id': 'ID автора',
        'reply_to': 'Ответ на',
        'reply_to_post_id': 'ID ответа',
        'quoted_post': 'Цитируемое сообщение',
        'quoted_post_id': 'ID цитируемого',
        'body': 'Текст',
        'is_topic_starter': 'Стартовое',
        'is_active': 'Активно',
        'replies': 'Ответы',
        'created_at': 'Создано',
        'updated_at': 'Обновлено',
    }
    name = 'Сообщение'
    name_plural = 'Сообщения'
    category = 'Форум'
    can_delete = False
    form_widget_args = {
        'body': {
            'rows': 8,
        },
    }
