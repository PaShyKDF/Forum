#!/bin/bash
set -e

if [ -z "${FORUM_TEST_DB_DATABASE+x}" ]; then
    echo "Переменная FORUM_TEST_DB_DATABASE не задана."
else
    echo "Тестовая БД: $FORUM_TEST_DB_DATABASE"

    echo "Ожидаем запуска PostgreSQL..."
    until pg_isready -U "$FORUM_DB_USER"; do
        echo "Ждем запуска PostgreSQL..."
        sleep 2
    done
    echo "PostgreSQL готов!"

    if psql -U "$FORUM_DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$FORUM_TEST_DB_DATABASE"; then
        echo "База '$FORUM_TEST_DB_DATABASE' уже существует."
    else
        psql -v ON_ERROR_STOP=1 \
            --username "$FORUM_DB_USER" \
            --dbname "$FORUM_DB_DATABASE" <<-EOSQL
            CREATE DATABASE $FORUM_TEST_DB_DATABASE;
            GRANT ALL PRIVILEGES ON DATABASE $FORUM_TEST_DB_DATABASE TO $FORUM_DB_USER;
EOSQL
        echo "База '$FORUM_TEST_DB_DATABASE' создана."
    fi
fi
