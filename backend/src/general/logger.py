import functools
import inspect
import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from pythonjsonlogger.json import JsonFormatter

from general.config import general_conf


LOG_DIR = os.environ.get('LOG_DIR', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'application.log')

_sentry_dsn = general_conf.external_logs_monitoring.sentry_dsn
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_logging = LoggingIntegration(
        level=None,
        event_level=getattr(
            logging,
            general_conf.log_level.external_log_level,
        ),
    )
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[sentry_logging],
        traces_sample_rate=1.0,
        send_default_pii=True,
        environment=(
            general_conf.external_logs_monitoring.environment
        ),
    )

stream_handler = logging.StreamHandler()
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8',
)


class CustomJsonFormatter(JsonFormatter):
    """Кастомный JSON-форматтер логов."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            now = (
                datetime.now(UTC)
                .replace(tzinfo=None)
                .strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            )
            log_record['timestamp'] = now
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread
        log_record['file'] = record.pathname
        log_record['line'] = record.lineno

    def format(self, record: logging.LogRecord) -> str:
        log_record = super().format(record)
        return json.dumps(
            json.loads(log_record),
            ensure_ascii=False,
        )


formatter = CustomJsonFormatter(
    '%(timestamp)s %(level)s %(message)s %(module)s '
    '%(funcName)s %(function)s %(func_args)s '
    '%(func_kwargs)s %(process_id)s %(thread_id)s '
    '%(file)s %(line)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(general_conf.log_level.default_log_level)

stream_handler.setFormatter(formatter)
stream_handler.setLevel(general_conf.log_level.local_log_level)

file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


def log(func):
    """Логирует исключения в sync/async функциях."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f'Исключение в {func.__name__}: {e}',
                    stack_info=True,
                    extra={
                        'func_args': args,
                        'func_kwargs': kwargs,
                        'func_name': func.__name__,
                        'func_module': func.__module__,
                    },
                )
                raise

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(
                f'Исключение в {func.__name__}: {e}',
                stack_info=True,
                extra={
                    'func_args': args,
                    'func_kwargs': kwargs,
                    'func_name': func.__name__,
                    'func_module': func.__module__,
                },
            )
            raise

    return sync_wrapper
