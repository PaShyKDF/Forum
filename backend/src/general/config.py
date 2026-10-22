from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from environs import Env


LogLevel: TypeAlias = Literal[
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL',
]

env = Env()
env.read_env(override=True)


@dataclass
class LogLevelConfig:
    """Конфигурация уровней логирования."""

    default_log_level: LogLevel = env(
        'FORUM_DEFAULT_LOG_LEVEL',
        'DEBUG',
    )
    local_log_level: LogLevel = env(
        'FORUM_LOCAL_LOG_LEVEL',
        'DEBUG',
    )
    external_log_level: LogLevel = env(
        'FORUM_EXTERNAL_LOG_LEVEL',
        'WARNING',
    )


@dataclass
class ExternalLogsMonitoringConfig:
    """Конфигурация внешнего мониторинга логов."""

    sentry_dsn: str = env('FORUM_SENTRY_DSN', '')
    environment: str = env(
        'FORUM_ENVIRONMENT',
        'development',
    )


@dataclass
class Configuration:
    """Общие конфигурации проекта."""

    log_level: LogLevelConfig = field(
        default_factory=LogLevelConfig,
    )
    external_logs_monitoring: ExternalLogsMonitoringConfig = field(
        default_factory=ExternalLogsMonitoringConfig,
    )


general_conf = Configuration()
