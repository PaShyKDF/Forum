#!/bin/bash

set -euo pipefail

echo "Запуск Forum API..."

echo "Ожидание готовности базы данных..."
sleep 5

echo "Проверка и применение миграций..."

if ! alembic-autogen-check --config forum/alembic.ini 2>/dev/null; then
    echo "Создание новой миграции..."
    alembic -c forum/alembic.ini revision --autogenerate \
        -m 'autogenerate'
fi

echo "Применение миграций..."
alembic -c forum/alembic.ini upgrade head

echo "Миграции применены!"

echo "Проверка раздела «Общий»..."
python -m forum.infrastructure.scripts.ensure_default_section

if [[ "${FORUM_MODE}" == "PROD" ]]; then
    echo "Запуск в PRODUCTION режиме..."
    gunicorn forum.entrypoint.fastapi_app:app \
        --workers "${FORUM_GUNICORN_WORKER_COUNT}" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind="${FORUM_FASTAPI_BIND_ADDRESS}:${FORUM_FASTAPI_CONTAINER_PORT}" \
        --forwarded-allow-ips='*'
else
    echo "Запуск в DEVELOPMENT режиме..."
    uvicorn forum.entrypoint.fastapi_app:app \
        --host 0.0.0.0 \
        --port "${FORUM_FASTAPI_CONTAINER_PORT}" \
        --forwarded-allow-ips='*' \
        --proxy-headers \
        --reload
fi
