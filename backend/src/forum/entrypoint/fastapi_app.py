"""Фабрика и точка входа FastAPI-приложения форума."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from forum.config import configuration
from forum.interfaces.admin.admin import RuAdmin
from forum.interfaces.admin.auth import authentication_backend
from forum.interfaces.admin.views import (
    CategoryAdmin,
    DirectChatAdmin,
    DirectMessageAdmin,
    PostAdmin,
    SectionAdmin,
    SupportTicketAdmin,
    TopicAdmin,
    TopicNotificationAdmin,
    UserAdmin,
)
from forum.interfaces.api.routers import (
    auth_router,
    categories_router,
    chats_router,
    contact_router,
    health_router,
    home_router,
    notifications_router,
    posts_router,
    sections_router,
    support_router,
    test_router,
    topics_router,
    users_router,
)
from forum.service_layer.keycloak_client import KeycloakClient
from forum.service_layer.tasks import example  # noqa: F401
from forum.service_layer.unit_of_work import async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan: общий httpx-клиент и KeycloakClient в app.state.

    Args:
        app: экземпляр FastAPI, которому пишется state.

    Yields:
        Управление после старта; по выходу клиент закрывается.
    """
    http_client = httpx.AsyncClient()
    app.state.keycloak_client = KeycloakClient(http_client)
    yield
    await http_client.aclose()


app = FastAPI(
    title='Forum API',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuration.cors.origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health_router)
app.include_router(auth_router, prefix='/api')
app.include_router(home_router, prefix='/api')
app.include_router(contact_router, prefix='/api')
app.include_router(support_router, prefix='/api')
app.include_router(sections_router, prefix='/api')
app.include_router(categories_router, prefix='/api')
app.include_router(topics_router, prefix='/api')
app.include_router(posts_router, prefix='/api')
app.include_router(chats_router, prefix='/api')
app.include_router(notifications_router, prefix='/api')
app.include_router(users_router, prefix='/api')
app.include_router(test_router, prefix='/api')

admin = RuAdmin(
    app,
    async_engine,
    authentication_backend=(
        authentication_backend
        if configuration.mode.enable_admin_auth
        else None
    ),
    templates_dir='forum/interfaces/admin/templates',
)
admin.add_view(SectionAdmin)
admin.add_view(CategoryAdmin)
admin.add_view(TopicAdmin)
admin.add_view(PostAdmin)
admin.add_view(UserAdmin)
admin.add_view(DirectChatAdmin)
admin.add_view(DirectMessageAdmin)
admin.add_view(TopicNotificationAdmin)
admin.add_view(SupportTicketAdmin)
