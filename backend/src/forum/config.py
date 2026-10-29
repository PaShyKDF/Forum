from dataclasses import dataclass, field
from typing import Literal

from environs import Env
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker


env = Env()
env.read_env()

DEFAULT_DB_POOL_SIZE = 5
DEFAULT_DB_MAX_OVERFLOW = 10
DEFAULT_REDIS_PORT = 6379


@dataclass
class ModeConfig:
    """Режим работы приложения."""

    mode: Literal['DEV', 'PROD', 'TEST'] = env(
        'FORUM_MODE',
        'DEV',
    )
    enable_admin_auth: bool = env.bool(
        'FORUM_ENABLE_ADMIN_AUTH',
        False,
    )

    def __post_init__(self):
        if self.mode not in ['DEV', 'PROD', 'TEST']:
            raise ValueError(f'Неподдерживаемый режим: {self.mode}')


@dataclass
class DatabaseConfig:
    """Конфигурация основной БД."""

    system: str = env('FORUM_DB_SYSTEM', 'postgresql')
    driver: str | None = env('FORUM_DB_DRIVER', 'asyncpg')
    name: str = env('FORUM_DB_DATABASE')
    user: str = env('FORUM_DB_USER')
    password: str = env('FORUM_DB_PASSWORD')
    port: int = env.int('FORUM_DB_CONTAINER_PORT', 5432)
    host: str = env('FORUM_DB_HOST', 'localhost')
    external_port: int = env.int('FORUM_DB_HOST_PORT', 5433)
    pool_size: int = env.int(
        'FORUM_DB_POOL_SIZE',
        DEFAULT_DB_POOL_SIZE,
    )
    max_overflow: int = env.int(
        'FORUM_DB_MAX_OVERFLOW',
        DEFAULT_DB_MAX_OVERFLOW,
    )

    def __post_init__(self):
        if not self.name:
            raise ValueError('Имя базы данных не может быть пустым')
        if not self.user:
            raise ValueError('Пользователь БД не может быть пустым')
        if not self.password:
            raise ValueError('Пароль БД не может быть пустым')

    @property
    def database_async_url(self) -> str:
        return (
            f'{self.system}+{self.driver}://'
            f'{self.user}:{self.password}@'
            f'{self.host}:{self.port}/{self.name}'
        )


@dataclass
class TestDatabaseConfig:
    """Конфигурация тестовой БД."""

    system: str = env('FORUM_TEST_DB_SYSTEM', 'postgresql')
    driver: str | None = env('FORUM_TEST_DB_DRIVER', 'asyncpg')
    name: str = env('FORUM_TEST_DB_DATABASE', 'forum_test')
    user: str = env('FORUM_TEST_DB_USER', 'postgres')
    passwd: str = env('FORUM_TEST_DB_PASSWORD', 'postgres')
    port: int = env.int('FORUM_TEST_DB_HOST_PORT', 5434)
    host: str = env('FORUM_TEST_DB_HOST', 'localhost')
    pool_size: int = env.int('FORUM_TEST_DB_POOL_SIZE', 5)
    max_overflow: int = env.int('FORUM_TEST_DB_MAX_OVERFLOW', 10)

    @property
    def database_async_url(self) -> str:
        return (
            f'{self.system}+{self.driver}://'
            f'{self.user}:{self.passwd}@'
            f'{self.host}:{self.port}/{self.name}'
        )


@dataclass
class RedisConfig:
    """Конфигурация Redis."""

    db: int = env.int('FORUM_REDIS_CACHE_DB', 0)
    host: str = env('FORUM_REDIS_CACHE_HOST', 'localhost')
    port: int = env.int(
        'FORUM_REDIS_CACHE_CONTAINER_PORT',
        DEFAULT_REDIS_PORT,
    )
    password: str | None = env('FORUM_REDIS_CACHE_PASSWORD', None)
    state_ttl: int | None = env.int(
        'FORUM_REDIS_CACHE_TTL_STATE',
        None,
    )
    data_ttl: int | None = env.int(
        'FORUM_REDIS_CACHE_TTL_DATA',
        None,
    )
    taskiq_db: int = env.int('FORUM_REDIS_TASKIQ_DB', 5)

    def __post_init__(self):
        if not self.host:
            raise ValueError('Хост Redis не может быть пустым')
        if not self.port:
            raise ValueError('Порт Redis не может быть пустым')


@dataclass
class CorsConfig:
    """CORS: разрешённые origins фронтенда."""

    origins: list[str] = field(
        default_factory=lambda: env.list(
            'FORUM_CORS_ORIGINS',
            [
                'http://localhost:3080',
                'http://127.0.0.1:3080',
            ],
        )
    )


@dataclass
class AdminConfig:
    """Доступ к SQLAdmin через Keycloak."""

    auth_secret_key: str = env(
        'FORUM_ADMIN_AUTH_SECRET_KEY',
        'change-me-forum-admin-secret',
    )
    # Realm/client role в Keycloak для доступа в /admin
    required_role: str = env('FORUM_ADMIN_ROLE', 'admin')


@dataclass
class KeycloakConfig:
    """Настройки Keycloak OIDC.

    public URL — редиректы браузера (auth/logout).
    internal URL — token/userinfo из API-контейнера.
    Для Docker: internal = host.docker.internal:<KC_PORT>,
    тот же frontend URL, что у браузера (не keycloak:8080).
    """

    CLIENT_ID: str = env('FORUM_KEYCLOAK_CLIENT_ID')
    CLIENT_SECRET: str = env('FORUM_KEYCLOAK_CLIENT_SECRET')
    BASE_URL: str = env('FORUM_BASE_URL')
    REALM: str = env('FORUM_KEYCLOAK_REALM')
    # Куда вернуть пользователя после OIDC login
    frontend_url: str = env(
        'FORUM_FRONTEND_URL',
        'http://localhost:3080',
    )
    # Браузер (localhost / публичный хост Keycloak)
    public_base_url: str = env('FORUM_KEYCLOAK_BASE_URL')
    # API → Keycloak внутри docker-сети
    internal_base_url: str = env(
        'FORUM_KEYCLOAK_INTERNAL_URL',
        env('FORUM_KEYCLOAK_BASE_URL'),
    )

    def _oidc_url(self, base: str, endpoint: str) -> str:
        return (
            f'{base}/realms/{self.REALM}'
            f'/protocol/openid-connect/{endpoint}'
        )

    @property
    def cookie_secure(self) -> bool:
        """True, если frontend отдаётся по https (Secure cookies)."""
        return self.frontend_url.startswith('https://')

    @property
    def token_url(self) -> str:
        """Token endpoint (server-side, internal_base_url)."""
        return self._oidc_url(
            self.internal_base_url,
            'token',
        )

    @property
    def userinfo_url(self) -> str:
        """Userinfo endpoint (server-side, internal_base_url)."""
        return self._oidc_url(
            self.internal_base_url,
            'userinfo',
        )

    @property
    def auth_url(self) -> str:
        """Authorization endpoint для редиректа браузера."""
        return self._oidc_url(
            self.public_base_url,
            'auth',
        )

    @property
    def logout_url(self) -> str:
        """End-session endpoint для редиректа браузера."""
        return self._oidc_url(
            self.public_base_url,
            'logout',
        )

    @property
    def redirect_uri(self) -> str:
        """OIDC callback форума (same-origin cookies через nginx)."""
        return (
            f'{self.frontend_url}/api/login/callback'
        )

    @property
    def admin_redirect_uri(self) -> str:
        """OIDC callback SQLAdmin (cookies на порту API)."""
        return f'{self.BASE_URL}/api/login/callback'

    @property
    def post_login_redirect(self) -> str:
        """Куда отправить пользователя после успешного входа на форум."""
        return f'{self.frontend_url}/#/'


@dataclass
class DiscussionsConfig:
    """Настройки обсуждений: редактирование, пагинация, антиспам."""

    post_edit_window_hours: int = env.int(
        'FORUM_POST_EDIT_WINDOW_HOURS',
        24,
    )
    topic_edit_window_hours: int = env.int(
        'FORUM_TOPIC_EDIT_WINDOW_HOURS',
        24,
    )
    roots_page_size: int = env.int(
        'FORUM_POSTS_ROOTS_PAGE_SIZE',
        20,
    )
    replies_page_size: int = env.int(
        'FORUM_POSTS_REPLIES_PAGE_SIZE',
        10,
    )
    # Минимальный интервал между сообщениями (сек)
    message_min_interval_seconds: int = env.int(
        'FORUM_MESSAGE_MIN_INTERVAL_SECONDS',
        10,
    )
    # Макс. сообщений за час
    posts_per_hour_limit: int = env.int(
        'FORUM_POSTS_PER_HOUR_LIMIT',
        30,
    )
    # Окно для лимита новых тем (сек), по умолчанию 10 мин
    topics_window_seconds: int = env.int(
        'FORUM_TOPICS_WINDOW_SECONDS',
        600,
    )
    # Макс. новых тем в окне topics_window_seconds
    topics_per_window_limit: int = env.int(
        'FORUM_TOPICS_PER_WINDOW_LIMIT',
        3,
    )
    # Макс. новых тем за сутки (МСК)
    topics_per_day_limit: int = env.int(
        'FORUM_TOPICS_PER_DAY_LIMIT',
        10,
    )

    def __post_init__(self):
        if self.post_edit_window_hours < 0:
            raise ValueError(
                'FORUM_POST_EDIT_WINDOW_HOURS '
                'не может быть отрицательным',
            )
        if self.topic_edit_window_hours < 0:
            raise ValueError(
                'FORUM_TOPIC_EDIT_WINDOW_HOURS '
                'не может быть отрицательным',
            )
        if self.roots_page_size < 1:
            raise ValueError(
                'FORUM_POSTS_ROOTS_PAGE_SIZE '
                'должен быть >= 1',
            )
        if self.replies_page_size < 1:
            raise ValueError(
                'FORUM_POSTS_REPLIES_PAGE_SIZE '
                'должен быть >= 1',
            )
        if self.message_min_interval_seconds < 1:
            raise ValueError(
                'FORUM_MESSAGE_MIN_INTERVAL_SECONDS '
                'должен быть >= 1',
            )
        if self.posts_per_hour_limit < 1:
            raise ValueError(
                'FORUM_POSTS_PER_HOUR_LIMIT '
                'должен быть >= 1',
            )
        if self.topics_window_seconds < 1:
            raise ValueError(
                'FORUM_TOPICS_WINDOW_SECONDS '
                'должен быть >= 1',
            )
        if self.topics_per_window_limit < 1:
            raise ValueError(
                'FORUM_TOPICS_PER_WINDOW_LIMIT '
                'должен быть >= 1',
            )
        if self.topics_per_day_limit < 1:
            raise ValueError(
                'FORUM_TOPICS_PER_DAY_LIMIT '
                'должен быть >= 1',
            )


@dataclass
class ContactConfig:
    """Ссылки страницы «Связаться»."""

    telegram_url: str = env(
        'FORUM_CONTACT_TELEGRAM_URL',
        'https://t.me/example',
    )
    whatsapp_url: str = env(
        'FORUM_CONTACT_WHATSAPP_URL',
        'https://wa.me/79000000000',
    )

    def __post_init__(self):
        for name, value in (
            ('FORUM_CONTACT_TELEGRAM_URL', self.telegram_url),
            ('FORUM_CONTACT_WHATSAPP_URL', self.whatsapp_url),
        ):
            cleaned = (value or '').strip()
            if not cleaned:
                raise ValueError(
                    f'{name} не может быть пустым',
                )
            if not cleaned.startswith('https://'):
                raise ValueError(
                    f'{name} должен начинаться с https://',
                )


@dataclass
class SupportConfig:
    """Лимиты обращений в техподдержку."""

    tickets_per_day_limit: int = env.int(
        'FORUM_SUPPORT_TICKETS_PER_DAY_LIMIT',
        2,
    )

    def __post_init__(self):
        if self.tickets_per_day_limit < 1:
            raise ValueError(
                'FORUM_SUPPORT_TICKETS_PER_DAY_LIMIT '
                'должен быть >= 1',
            )


@dataclass
class VisitorsConfig:
    """Трекинг гостей (anon cookie)."""

    # Минимальный интервал обновления last_seen_at
    touch_interval_seconds: int = env.int(
        'FORUM_VISITOR_TOUCH_INTERVAL_SECONDS',
        300,
    )
    # TTL cookie forum_anon_id (секунды), ~1 год
    anon_cookie_max_age: int = env.int(
        'FORUM_VISITOR_ANON_COOKIE_MAX_AGE',
        31_536_000,
    )
    # Local Docker: peer = 172.x gateway, публичный IP
    # через egress lookup (ip-api). В PROD выкл. по умолчанию.
    use_egress_ip_when_private: bool = env.bool(
        'FORUM_VISITORS_USE_EGRESS_IP_WHEN_PRIVATE',
        env('FORUM_MODE', 'DEV') == 'DEV',
    )
    # Периодическая очистка устаревших гостей (TaskIQ)
    cleanup_enabled: bool = env.bool(
        'FORUM_VISITORS_CLEANUP_ENABLED',
        True,
    )
    # Сколько дней без активности хранить гостя
    cleanup_retention_days: int = env.int(
        'FORUM_VISITORS_CLEANUP_RETENTION_DAYS',
        7,
    )
    # Cron TaskIQ (UTC). 0 0 * * * = 03:00 МСК
    cleanup_cron: str = env(
        'FORUM_VISITORS_CLEANUP_CRON',
        '0 0 * * *',
    )
    cleanup_batch_size: int = env.int(
        'FORUM_VISITORS_CLEANUP_BATCH_SIZE',
        500,
    )
    cleanup_max_batches: int = env.int(
        'FORUM_VISITORS_CLEANUP_MAX_BATCHES',
        1000,
    )

    def __post_init__(self):
        if self.touch_interval_seconds < 1:
            raise ValueError(
                'FORUM_VISITOR_TOUCH_INTERVAL_SECONDS '
                'должен быть >= 1',
            )
        if self.anon_cookie_max_age < 60:
            raise ValueError(
                'FORUM_VISITOR_ANON_COOKIE_MAX_AGE '
                'должен быть >= 60',
            )
        if self.cleanup_retention_days < 1:
            raise ValueError(
                'FORUM_VISITORS_CLEANUP_RETENTION_DAYS '
                'должен быть >= 1',
            )
        if self.cleanup_batch_size < 1:
            raise ValueError(
                'FORUM_VISITORS_CLEANUP_BATCH_SIZE '
                'должен быть >= 1',
            )
        if self.cleanup_max_batches < 1:
            raise ValueError(
                'FORUM_VISITORS_CLEANUP_MAX_BATCHES '
                'должен быть >= 1',
            )
        if not (self.cleanup_cron or '').strip():
            raise ValueError(
                'FORUM_VISITORS_CLEANUP_CRON '
                'не может быть пустым',
            )


@dataclass
class NotificationsCleanupConfig:
    """Суточная очистка неактивных уведомлений."""

    enabled: bool = env.bool(
        'FORUM_NOTIFICATIONS_CLEANUP_ENABLED',
        True,
    )
    batch_size: int = env.int(
        'FORUM_NOTIFICATIONS_CLEANUP_BATCH_SIZE',
        500,
    )
    max_batches: int = env.int(
        'FORUM_NOTIFICATIONS_CLEANUP_MAX_BATCHES',
        1000,
    )
    # Cron TaskIQ (UTC). По умолчанию 03:00 UTC
    cleanup_cron: str = env(
        'FORUM_NOTIFICATIONS_CLEANUP_CRON',
        '0 3 * * *',
    )

    def __post_init__(self):
        if self.batch_size < 1:
            raise ValueError(
                'FORUM_NOTIFICATIONS_CLEANUP_BATCH_SIZE '
                'должен быть >= 1',
            )
        if self.max_batches < 1:
            raise ValueError(
                'FORUM_NOTIFICATIONS_CLEANUP_MAX_BATCHES '
                'должен быть >= 1',
            )
        if not (self.cleanup_cron or '').strip():
            raise ValueError(
                'FORUM_NOTIFICATIONS_CLEANUP_CRON '
                'не может быть пустым',
            )


@dataclass
class TopicViewsConfig:
    """Хранение и очистка ежедневных просмотров тем."""

    # Сколько суток МСК хранить, включая сегодня
    retention_days: int = env.int(
        'FORUM_TOPIC_VIEWS_RETENTION_DAYS',
        30,
    )
    cleanup_enabled: bool = env.bool(
        'FORUM_TOPIC_VIEWS_CLEANUP_ENABLED',
        True,
    )
    # Cron TaskIQ (UTC). 30 0 * * * = 00:30 UTC
    cleanup_cron: str = env(
        'FORUM_TOPIC_VIEWS_CLEANUP_CRON',
        '30 0 * * *',
    )
    cleanup_batch_size: int = env.int(
        'FORUM_TOPIC_VIEWS_CLEANUP_BATCH_SIZE',
        500,
    )
    cleanup_max_batches: int = env.int(
        'FORUM_TOPIC_VIEWS_CLEANUP_MAX_BATCHES',
        1000,
    )

    def __post_init__(self):
        if self.retention_days < 1:
            raise ValueError(
                'FORUM_TOPIC_VIEWS_RETENTION_DAYS '
                'должен быть >= 1',
            )
        if self.cleanup_batch_size < 1:
            raise ValueError(
                'FORUM_TOPIC_VIEWS_CLEANUP_BATCH_SIZE '
                'должен быть >= 1',
            )
        if self.cleanup_max_batches < 1:
            raise ValueError(
                'FORUM_TOPIC_VIEWS_CLEANUP_MAX_BATCHES '
                'должен быть >= 1',
            )
        if not (self.cleanup_cron or '').strip():
            raise ValueError(
                'FORUM_TOPIC_VIEWS_CLEANUP_CRON '
                'не может быть пустым',
            )


@dataclass
class Configuration:
    """Корневая конфигурация форума."""

    mode: ModeConfig = field(default_factory=ModeConfig)
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    test_db: TestDatabaseConfig = field(
        default_factory=TestDatabaseConfig,
    )
    redis: RedisConfig = field(default_factory=RedisConfig)
    cors: CorsConfig = field(default_factory=CorsConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    keycloak: KeycloakConfig = field(default_factory=KeycloakConfig)
    discussions: DiscussionsConfig = field(
        default_factory=DiscussionsConfig,
    )
    contact: ContactConfig = field(
        default_factory=ContactConfig,
    )
    support: SupportConfig = field(
        default_factory=SupportConfig,
    )
    visitors: VisitorsConfig = field(
        default_factory=VisitorsConfig,
    )
    notifications_cleanup: NotificationsCleanupConfig = (
        field(
            default_factory=NotificationsCleanupConfig,
        )
    )
    topic_views: TopicViewsConfig = field(
        default_factory=TopicViewsConfig,
    )


configuration = Configuration()

taskiq_broker = ListQueueBroker(
    f'redis://:{configuration.redis.password}@'
    f'{configuration.redis.host}:'
    f'{configuration.redis.port}/'
    f'{configuration.redis.taskiq_db}'
)

taskiq_scheduler = TaskiqScheduler(
    broker=taskiq_broker,
    sources=[LabelScheduleSource(taskiq_broker)],
)
