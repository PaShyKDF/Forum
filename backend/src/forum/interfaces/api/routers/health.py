from fastapi import APIRouter


health_router = APIRouter(tags=['health'])


@health_router.get('/health')
async def health_check():
    """
    Проверка живости приложения (liveness).

    Returns:
        Словарь ``{'status': 'healthy'}``.
    """
    return {'status': 'healthy'}
