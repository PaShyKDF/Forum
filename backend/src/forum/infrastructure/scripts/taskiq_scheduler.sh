#!/bin/bash

set -e

echo "Запуск планировщика Taskiq..."

host="${FORUM_REDIS_CACHE_HOST:-redis}"
port="${FORUM_REDIS_CACHE_CONTAINER_PORT:-6379}"
echo "Ожидаю Redis на ${host}:${port}..."
for i in {1..60}; do
    if (exec 3<>/dev/tcp/${host}/${port}) 2>/dev/null; then
        exec 3>&-
        exec 3<&-
        echo "Redis доступен."
        break
    fi
    sleep 1
done

taskiq scheduler forum.entrypoint.taskiq_scheduler:scheduler
