# Backend форума

Архитектура перенесена из `Exp_And_Drive`: FastAPI + PostgreSQL/SQLAlchemy +
Unit of Work + MessageBus (CQRS) + Taskiq (очередь задач) + Alembic.

## Быстрый старт

```bash
cd Форум
cp .env.example .env   # если ещё нет .env
docker compose up --build
```

Сервисы (порты из `.env`):
- Frontend: http://localhost:3080
- API: http://localhost:8077 (или `FORUM_FASTAPI_HOST_PORT`)
- Swagger: http://localhost:8077/docs
- Health: http://localhost:8077/health
- PGAdmin: http://localhost:5061
- Redis / PostgreSQL — см. `.env`

CORS: `FORUM_CORS_ORIGINS` (по умолчанию
`http://localhost:3080` и `http://127.0.0.1:3080`).
Базовый URL API на фронте: `frontend/src/config.js`.

Админка SQLAdmin: http://localhost:8077/admin/
(`FORUM_ENABLE_ADMIN_AUTH=false` — без логина;
при `true` — Keycloak, доступ только с ролью
`FORUM_ADMIN_ROLE`, по умолчанию `admin`).
pgAdmin (БД): http://localhost:5061

## Структура

```
backend/src/
├── general/                 # общие конфиг и логгер
└── forum/
    ├── config.py            # настройки + Taskiq broker
    ├── alembic.ini
    ├── adapters/
    │   ├── redis_client.py
    │   └── repositories/    # репозитории (base + ваши)
    ├── domain/
    │   ├── models/          # SQLAlchemy модели
    │   ├── schemas/         # Pydantic схемы
    │   ├── commands/        # команды CQRS
    │   ├── events/          # события
    │   └── exceptions.py
    ├── service_layer/
    │   ├── unit_of_work.py
    │   ├── messagebus.py
    │   ├── handlers/        # обработчики команд/событий
    │   └── tasks/           # фоновые Taskiq-задачи
    ├── interfaces/api/routers/
    ├── entrypoint/          # FastAPI + Taskiq worker/scheduler
    └── infrastructure/      # Docker, scripts, migrations
```

## Как добавить модель

1. Создайте файл в `domain/models/`, например `posts.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from forum.domain.models.base import Base
from forum.domain.models.mixins import IDMixin, CreatedAtMixin


class Post(Base, IDMixin, CreatedAtMixin):
    title: Mapped[str] = mapped_column(String, nullable=False)
```

2. Импортируйте модель в `domain/models/__init__.py` и добавьте в `__all__`.
3. При следующем старте API `app.sh` сам сделает
   `revision --autogenerate` (если модели отличаются от БД)
   и `upgrade head`. Файлы ревизий пишутся в Docker volume
   `alembic_versions`, в git их коммитить не нужно.

## Как добавить репозиторий

1. Создайте класс на базе `SQLAlchemyRepository` в `adapters/repositories/`.
2. Экспортируйте в `adapters/repositories/__init__.py`.
3. Подключите в `UnitOfWork.__aenter__`:

```python
self.post_repository = PostRepository(self.session)
```

## Как добавить эндпоинт

1. Команда в `domain/commands/`.
2. Handler в `service_layer/handlers/`, регистрация в `handlers/__init__.py`.
3. Router в `interfaces/api/routers/`.
4. `app.include_router(...)` в `entrypoint/fastapi_app.py`.

## Очередь задач (Taskiq)

Задачи живут в `service_layer/tasks/`. Пример вызова из API:

```python
from forum.service_layer.tasks.example import example_background_task

await example_background_task.kiq('текст')
```

Демо-эндпоинты:
- `POST /api/demo/echo` — MessageBus
- `POST /api/demo/enqueue` — постановка в очередь
- `POST /api/test` — ещё один тест MessageBus

## Production: app и Keycloak раздельно

Локально: `docker compose up` из корня репозитория
(всё в `docker-compose.yaml`).

На VPS:

1. Сеть (один раз): `docker network create forum_public_net`
2. IdP: `docker compose -p forum-idp -f docker-compose.keycloak.prod.yaml up -d`
3. App: `docker compose -p forum-app -f docker-compose.app.prod.yaml up -d --build`

CI приложения трогает только app-стек. IdP обновляется
отдельным редким job. Подробности — корневой `README.md`.

## Переменные окружения

Префикс `FORUM_*`. Шаблон — `.env.example`.

Для split-prod дополнительно:

- `FORUM_KC_HOSTNAME` — hostname Keycloak для iss
- `FORUM_KEYCLOAK_INTERNAL_URL=http://keycloak:8080`
- `FORUM_DOCKER_NETWORK=forum_public_net`
