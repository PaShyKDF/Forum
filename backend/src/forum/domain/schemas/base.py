from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """Базовый класс Pydantic-схем."""

    model_config = {
        'from_attributes': True,
        'populate_by_name': True,
        'str_strip_whitespace': True,
        'validate_assignment': True,
    }


class SuccessResponse(BaseSchema):
    """Универсальный успешный ответ."""

    success: bool = Field(True, description='Статус операции')
    message: str = Field(..., description='Сообщение')
