from .auth import router as auth_router
from .categories import home_router, router as categories_router
from .chats import router as chats_router
from .contact import router as contact_router
from .health import health_router
from .notifications import router as notifications_router
from .posts import router as posts_router
from .sections import router as sections_router
from .support import router as support_router
from .test import test_router
from .topics import router as topics_router
from .users import router as users_router


__all__ = [
    'auth_router',
    'categories_router',
    'chats_router',
    'contact_router',
    'health_router',
    'home_router',
    'notifications_router',
    'posts_router',
    'sections_router',
    'support_router',
    'test_router',
    'topics_router',
    'users_router',
]
