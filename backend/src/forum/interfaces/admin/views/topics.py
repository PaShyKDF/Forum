from forum.domain.models import Topic
from forum.interfaces.admin.views.base import BaseModelView


class TopicAdmin(BaseModelView, model=Topic):
    """Темы форума."""

    column_list = [
        'id',
        'title',
        'category',
        'author',
        'position',
        'is_topic',
        'is_pinned',
        'is_closed',
        'is_restricted',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'posts',
        'access_rows',
        'created_at',
        'updated_at',
    ]
    form_ajax_refs = {
        'allowed_users': {
            'fields': ('display_name', 'username', 'email'),
            'order_by': 'display_name',
        },
        'category': {
            'fields': ('title',),
            'order_by': 'title',
        },
        'author': {
            'fields': ('display_name', 'username'),
            'order_by': 'display_name',
        },
    }
    column_searchable_list = ['title']
    column_sortable_list = [
        'id',
        'title',
        'position',
        'is_topic',
        'is_pinned',
        'is_closed',
        'is_restricted',
        'is_active',
        'views_count',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'title': 'Название',
        'description': 'Описание',
        'category': 'Категория',
        'category_id': 'ID категории',
        'author': 'Автор',
        'author_id': 'ID автора',
        'position': 'Позиция',
        'is_topic': 'Спец. раздел',
        'is_pinned': 'Закреплена',
        'is_closed': 'Закрыта',
        'is_restricted': 'Скрытая',
        'is_active': 'Активна',
        'allowed_users': 'Допущенные пользователи',
        'views_count': 'Просмотры',
        'posts': 'Сообщения',
        'created_at': 'Создана',
        'updated_at': 'Обновлена',
    }
    name = 'Тема'
    name_plural = 'Темы'
    category = 'Форум'
    can_delete = False
