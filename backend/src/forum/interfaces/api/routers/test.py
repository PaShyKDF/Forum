from fastapi import APIRouter, Depends

from forum.domain.commands import EchoTestCommand
from forum.domain.schemas import SuccessResponse
from forum.service_layer.messagebus import MessageBus, get_message_bus
# from forum.service_layer.tasks.example import example_background_task


test_router = APIRouter(prefix='/demo', tags=['demo'])


@test_router.post('/echo', response_model=SuccessResponse)
async def echo(
    message: str = 'Привет мир!',
    message_bus: MessageBus = Depends(get_message_bus),
):
    """
    Демо CQRS: EchoTestCommand через MessageBus.

    Args:
        message: строка для эха.
        message_bus: Depends MessageBus.

    Returns:
        SuccessResponse с результатом команды.
    """
    result = await message_bus.handle(
        EchoTestCommand(message=message),
    )
    return SuccessResponse(message=str(result))

# @test_router.post('/enqueue')
# async def enqueue_task(message: str = 'фоновая задача'):
#     """Демо постановки задачи в очередь Taskiq."""
#     task = await example_background_task.kiq(message)
#     return {
#         'status': 'queued',
#         'task_id': task.task_id,
#         'message': message,
#     }
