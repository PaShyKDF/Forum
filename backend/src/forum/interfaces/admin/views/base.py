from sqladmin import ModelView

from forum.service_layer.timeutils import (
    format_moscow_datetime_value,
)


def format_moscow_datetime(model_obj, field_name):
    """Форматирует datetime из UTC в московское время (+3)."""
    datetime_value = getattr(model_obj, field_name, None)
    return format_moscow_datetime_value(datetime_value)


def format_moscow_datetime_detail(model_obj, attribute):
    field_name = getattr(attribute, 'key', None) or str(attribute)
    return format_moscow_datetime(model_obj, field_name)


class BaseModelView(ModelView):
    """Базовый ModelView с московским временем."""

    column_formatters = {
        'created_at': format_moscow_datetime,
        'updated_at': format_moscow_datetime,
        'last_seen_at': format_moscow_datetime,
    }
    column_formatters_detail = {
        'created_at': format_moscow_datetime_detail,
        'updated_at': format_moscow_datetime_detail,
        'last_seen_at': format_moscow_datetime_detail,
    }
