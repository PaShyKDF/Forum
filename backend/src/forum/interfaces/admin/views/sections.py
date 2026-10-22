from forum.domain.models import Section
from forum.interfaces.admin.views.base import BaseModelView


class SectionAdmin(BaseModelView, model=Section):
    """Разделы форума."""

    column_list = [
        'id',
        'title',
        'position',
        'is_topic',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'categories',
        'created_at',
        'updated_at',
    ]
    column_searchable_list = ['title']
    column_sortable_list = [
        'id',
        'title',
        'position',
        'is_topic',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'title': 'Название',
        'position': 'Позиция',
        'is_topic': 'Спец. раздел',
        'is_active': 'Активен',
        'categories': 'Категории',
        'created_at': 'Создан',
        'updated_at': 'Обновлён',
    }
    name = 'Раздел'
    name_plural = 'Разделы'
    category = 'Форум'
    can_delete = False
