# Keycloak SPI: согласие с правилами при регистрации

Серверная проверка галочки на форме регистрации.
Без поля `termsAccepted` Keycloak отклоняет создание аккаунта,
даже если в HTML убрать `required`.

## Состав

- `forum-registration-terms/` — исходники FormAction SPI
  (`registration-terms-and-conditions`)
- `providers/forum-registration-terms.jar` — собранный провайдер
  (монтируется в контейнер Keycloak)
- `scripts/enable-registration-terms.sh` — включает шаг в
  Authentication flow realm `Forum`

## Как это работает

1. SPI регистрирует FormAction `registration-terms-and-conditions`.
2. В registration form flow шаг должен быть **REQUIRED**.
3. `buildPage` передаёт в шаблон `termsAcceptanceRequired=true`.
4. Тема `themes/forum/login/register.ftl` показывает чекбокс
   `name="termsAccepted"`.
5. `validate` отклоняет POST без `termsAccepted`.

## Подключение

JAR уже монтируется через `docker-compose.yaml`:

```yaml
./keycloak-spi/providers -> /opt/keycloak/providers
```

После изменения JAR перезапустите Keycloak:

```bash
docker compose up -d --force-recreate keycloak
```

Включите шаг в flow (нужен admin Keycloak):

```bash
chmod +x keycloak-spi/scripts/enable-registration-terms.sh
./keycloak-spi/scripts/enable-registration-terms.sh
```

Или вручную в Admin Console:

1. Realm **Forum** → Authentication → Flows → **registration**
2. Откройте **registration form**
3. Add step / Add execution → **Terms and conditions**
4. Requirement = **REQUIRED**

## Сборка JAR (опционально)

Нужен Maven и JDK 11+:

```bash
cd keycloak-spi/forum-registration-terms
mvn -q package
cp target/forum-registration-terms.jar ../providers/
```

## Тема

- Чекбокс: `themes/forum/login/register.ftl`
- Сообщение об ошибке: `termsAcceptanceRequired` в
  `themes/forum/login/messages/messages_ru.properties`
