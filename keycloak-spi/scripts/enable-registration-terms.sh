#!/usr/bin/env bash
# Включает FormAction «Terms and conditions» в registration flow realm.
# Без этого шага серверная проверка галочки не работает.
#
# Usage:
#   ./keycloak-spi/scripts/enable-registration-terms.sh
#
# Env (optional):
#   KC_URL          default http://localhost:8282
#   KC_REALM        default Forum
#   KC_ADMIN_USER   default from FORUM_KC_ADMIN_LOGIN / admin
#   KC_ADMIN_PASS   default from FORUM_KC_ADMIN_PASSWORD / admin
#   KC_PROVIDER_ID  default registration-terms-and-conditions

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
fi

KC_URL="${KC_URL:-${FORUM_KEYCLOAK_BASE_URL:-http://localhost:8282}}"
KC_REALM="${KC_REALM:-${FORUM_KEYCLOAK_REALM:-Forum}}"
KC_ADMIN_USER="${KC_ADMIN_USER:-${FORUM_KC_ADMIN_LOGIN:-admin}}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-${FORUM_KC_ADMIN_PASSWORD:-admin}}"
KC_PROVIDER_ID="${KC_PROVIDER_ID:-registration-terms-and-conditions}"

echo "Keycloak: ${KC_URL}, realm=${KC_REALM}, provider=${KC_PROVIDER_ID}"

TOKEN_RESP="$(
  curl -sS -X POST \
    "${KC_URL}/realms/master/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "username=${KC_ADMIN_USER}" \
    --data-urlencode "password=${KC_ADMIN_PASS}" \
    --data-urlencode 'grant_type=password' \
    --data-urlencode 'client_id=admin-cli'
)"

TOKEN="$(
  printf '%s' "${TOKEN_RESP}" | python3 -c '
import sys, json
data = json.load(sys.stdin)
token = data.get("access_token")
if not token:
    print(data, file=sys.stderr)
    raise SystemExit("Не удалось получить admin token")
print(token)
'
)"

auth_hdr=(-H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json')

FLOWS_JSON="$(
  curl -sS "${auth_hdr[@]}" \
    "${KC_URL}/admin/realms/${KC_REALM}/authentication/flows"
)"

REG_FORM_ALIAS="$(
  printf '%s' "${FLOWS_JSON}" | python3 -c '
import sys, json
flows = json.load(sys.stdin)
candidates = []
for flow in flows:
    alias = flow.get("alias") or ""
    provider = flow.get("providerId") or ""
    low = alias.lower()
    if provider == "form-flow" and (
        "registration" in low and "form" in low
    ):
        candidates.append(alias)
if not candidates:
    for flow in flows:
        alias = (flow.get("alias") or "")
        if alias.lower() == "registration form":
            candidates.append(alias)
if not candidates:
    raise SystemExit(
        "Не найден registration form flow. "
        "Проверьте Authentication → Flows в Admin Console."
    )
print(candidates[0])
'
)"

echo "Registration form alias: ${REG_FORM_ALIAS}"

find_execution_id() {
  local json="$1"
  printf '%s' "${json}" | python3 -c '
import sys, json, os
provider = os.environ["KC_PROVIDER_ID"]
execs = json.load(sys.stdin)
for item in execs:
    if item.get("providerId") == provider:
        print(item.get("id") or "")
        raise SystemExit(0)
print("")
'
}

export KC_PROVIDER_ID

EXECUTIONS_JSON="$(
  curl -sS "${auth_hdr[@]}" \
    "${KC_URL}/admin/realms/${KC_REALM}/authentication/flows/${REG_FORM_ALIAS}/executions"
)"

ALREADY="$(find_execution_id "${EXECUTIONS_JSON}")"

if [[ -z "${ALREADY}" ]]; then
  echo "Добавляю execution ${KC_PROVIDER_ID}..."
  HTTP_CODE="$(
    curl -sS -o /tmp/kc-add-exec.out -w '%{http_code}' -X POST \
      "${auth_hdr[@]}" \
      "${KC_URL}/admin/realms/${KC_REALM}/authentication/flows/${REG_FORM_ALIAS}/executions/execution" \
      -d "{\"provider\":\"${KC_PROVIDER_ID}\"}"
  )"
  echo "add execution http=${HTTP_CODE}"
  if [[ "${HTTP_CODE}" != "201" && "${HTTP_CODE}" != "204" && "${HTTP_CODE}" != "200" ]]; then
    cat /tmp/kc-add-exec.out >&2 || true
    exit 1
  fi
  EXECUTIONS_JSON="$(
    curl -sS "${auth_hdr[@]}" \
      "${KC_URL}/admin/realms/${KC_REALM}/authentication/flows/${REG_FORM_ALIAS}/executions"
  )"
  ALREADY="$(find_execution_id "${EXECUTIONS_JSON}")"
else
  echo "Execution уже есть: ${ALREADY}"
fi

if [[ -z "${ALREADY}" ]]; then
  echo "Не удалось найти execution после добавления." >&2
  exit 1
fi

echo "Ставлю requirement=REQUIRED..."
HTTP_CODE="$(
  curl -sS -o /tmp/kc-req.out -w '%{http_code}' -X PUT \
    "${auth_hdr[@]}" \
    "${KC_URL}/admin/realms/${KC_REALM}/authentication/flows/${REG_FORM_ALIAS}/executions" \
    -d "{\"id\":\"${ALREADY}\",\"requirement\":\"REQUIRED\"}"
)"
echo "set requirement http=${HTTP_CODE}"
if [[ "${HTTP_CODE}" != "202" && "${HTTP_CODE}" != "204" && "${HTTP_CODE}" != "200" ]]; then
  cat /tmp/kc-req.out >&2 || true
  exit 1
fi

echo "Готово. Без галочки termsAccepted регистрация будет отклонена сервером."
