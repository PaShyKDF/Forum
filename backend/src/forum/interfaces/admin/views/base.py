from typing import Any

from sqladmin import ModelView
from starlette.exceptions import HTTPException
from starlette.requests import Request

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
    """
    Базовый ModelView с московским временем и удалением.

    Удаление требует query confirm=1 (чекбокс в модалке).
    """

    can_delete = True
    delete_warning = (
        'Будут безвозвратно удалены выбранные записи '
        'и связанные с ними данные.'
    )

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

    async def delete_model(
        self,
        request: Request,
        pk: Any,
    ) -> None:
        """
        Удаляет модель только при confirm=1.

        Args:
            request: HTTP-запрос админки.
            pk: первичный ключ записи.

        Raises:
            HTTPException: 400 без подтверждения.
        """
        if request.query_params.get('confirm') != '1':
            raise HTTPException(
                status_code=400,
                detail=(
                    'Нужно подтвердить удаление '
                    '(чекбокс согласия)'
                ),
            )
        await super().delete_model(request, pk)
