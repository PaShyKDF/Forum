from forum.domain.models import Category
from forum.interfaces.admin.views.base import BaseModelView


class CategoryAdmin(BaseModelView, model=Category):
    """Категории форума."""

    column_list = [
        'id',
        'title',
        'section',
        'position',
        'is_restricted',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'topics',
        'access_rows',
        'created_at',
        'updated_at',
    ]
    form_ajax_refs = {
        'allowed_users': {
            'fields': ('display_name', 'username', 'email'),
            'order_by': 'display_name',
        },
        'section': {
            'fields': ('title',),
            'order_by': 'position',
        },
    }
    column_searchable_list = ['title']
    column_sortable_list = [
        'id',
        'title',
        'position',
        'is_restricted',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'title': 'Название',
        'description': 'Описание',
        'section': 'Раздел',
        'section_id': 'ID раздела',
        'position': 'Позиция',
        'is_restricted': 'Скрытая',
        'is_active': 'Активна',
        'allowed_users': 'Допущенные пользователи',
        'topics': 'Темы',
        'created_at': 'Создана',
        'updated_at': 'Обновлена',
    }
    name = 'Категория'
    name_plural = 'Категории'
    category = 'Форум'
    can_delete = False
