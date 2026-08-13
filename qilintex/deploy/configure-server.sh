#!/usr/bin/env bash
set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:?请设置 PUBLIC_HOST，例如 example.com 或 203.0.113.10}"
WWW_HOST="${WWW_HOST:-www.${PUBLIC_HOST}}"
UPDATE_HOST="${UPDATE_HOST:-updates.${PUBLIC_HOST}}"
LEGACY_HOST="${LEGACY_HOST:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
DATA_ROOT="${DATA_ROOT:-/var/lib/qilintex}"
UPDATE_ROOT="${UPDATE_ROOT:-${DATA_ROOT}/updates}"
CONFIG_ROOT="${CONFIG_ROOT:-/etc/qilintex}"
SERVICE_USER="${SERVICE_USER:-qilintex}"
SERVICE_GROUP="${SERVICE_GROUP:-${SERVICE_USER}}"
NODE_BIN="${NODE_BIN:-$(command -v node)}"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  (cd -- "${APP_ROOT}" && pnpm install --frozen-lockfile && pnpm setup && pnpm build)
fi
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  sudo useradd --system --home-dir "${DATA_ROOT}" --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 750 "${DATA_ROOT}"
sudo install -d -o root -g root -m 755 "${UPDATE_ROOT}"
sudo install -d -o root -g "${SERVICE_GROUP}" -m 750 "${CONFIG_ROOT}"

temporary_env="$(mktemp)"
temporary_caddy="$(mktemp)"
temporary_service="$(mktemp)"
trap 'rm -f "$temporary_env" "$temporary_caddy" "$temporary_service"' EXIT
environment_created=0
if sudo test -f "${CONFIG_ROOT}/qilintex.env" && [[ "${RESET_ENV:-0}" != "1" ]]; then
  sudo cat "${CONFIG_ROOT}/qilintex.env" >"$temporary_env"
  ensure_env() {
    local key="$1"
    local value="$2"
    if ! grep -q "^${key}=" "$temporary_env"; then
      printf '%s=%s\n' "$key" "$value" >>"$temporary_env"
    fi
  }
  ensure_env HOME "${DATA_ROOT}"
  set_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$temporary_env"; then
      sed -i "s|^${key}=.*$|${key}=${value}|" "$temporary_env"
    else
      printf '%s=%s\n' "$key" "$value" >>"$temporary_env"
    fi
  }
  set_env CLIENT_URL "https://${PUBLIC_HOST}"
  set_env CLIENT_URLS "https://${PUBLIC_HOST}${LEGACY_HOST:+,http://${LEGACY_HOST}}"
  set_env PUBLIC_API_URL "https://${PUBLIC_HOST}"
  set_env PUBLIC_COLLAB_URL "wss://${PUBLIC_HOST}/collab"
  set_env QQ_REDIRECT_URI "https://${PUBLIC_HOST}/auth/qq/callback"
  set_env WECHAT_REDIRECT_URI "https://${PUBLIC_HOST}/auth/wechat/callback"
  set_env APP_LATEST_VERSION "${APP_LATEST_VERSION:-0.1.2}"
else
  TEAM_CODE="QT-$(openssl rand -hex 6)"
  SESSION_SECRET="$(openssl rand -hex 48)"
  environment_created=1
  cat >"$temporary_env" <<EOF
NODE_ENV=production
HOST=127.0.0.1
HOME=${DATA_ROOT}
PORT=4318
COLLAB_PORT=4319
CLIENT_URL=https://${PUBLIC_HOST}
CLIENT_URLS=https://${PUBLIC_HOST}${LEGACY_HOST:+,http://${LEGACY_HOST}}
PUBLIC_API_URL=https://${PUBLIC_HOST}
PUBLIC_COLLAB_URL=wss://${PUBLIC_HOST}/collab
SESSION_SECRET=${SESSION_SECRET}
ALLOW_DEV_LOGIN=false
TEAM_NAME=数模工作台内部团队
TEAM_ACCESS_CODE=${TEAM_CODE}
DATA_DIR="${DATA_ROOT}"
QQ_APP_ID=
QQ_APP_SECRET=
QQ_REDIRECT_URI=https://${PUBLIC_HOST}/auth/qq/callback
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_REDIRECT_URI=https://${PUBLIC_HOST}/auth/wechat/callback
APP_LATEST_VERSION=${APP_LATEST_VERSION:-0.1.2}
TEX_ENGINE=latexmk
TEX_LATEXMK_ENGINE=xelatex
EOF
fi

escape_sed() { printf '%s' "$1" | sed 's/[&|]/\\&/g'; }
escaped_app_root="$(escape_sed "${APP_ROOT}")"
escaped_data_root="$(escape_sed "${DATA_ROOT}")"
escaped_config_root="$(escape_sed "${CONFIG_ROOT}")"
escaped_update_root="$(escape_sed "${UPDATE_ROOT}")"
escaped_node_bin="$(escape_sed "${NODE_BIN}")"

sudo install -o root -g "${SERVICE_GROUP}" -m 640 "$temporary_env" "${CONFIG_ROOT}/qilintex.env"
sed \
  -e "s|__SERVICE_USER__|$(escape_sed "${SERVICE_USER}")|g" \
  -e "s|__SERVICE_GROUP__|$(escape_sed "${SERVICE_GROUP}")|g" \
  -e "s|__APP_ROOT__|${escaped_app_root}|g" \
  -e "s|__CONFIG_ROOT__|${escaped_config_root}|g" \
  -e "s|__DATA_ROOT__|${escaped_data_root}|g" \
  -e "s|__NODE_BIN__|${escaped_node_bin}|g" \
  "${SCRIPT_DIR}/qilintex.service" >"$temporary_service"
sudo install -m 644 "$temporary_service" /etc/systemd/system/qilintex.service

sed \
  -e "s|__PUBLIC_HOST__|$(escape_sed "${PUBLIC_HOST}")|g" \
  -e "s|__WWW_HOST__|$(escape_sed "${WWW_HOST}")|g" \
  -e "s|__UPDATE_HOST__|$(escape_sed "${UPDATE_HOST}")|g" \
  -e "s|__APP_ROOT__|${escaped_app_root}|g" \
  -e "s|__UPDATE_ROOT__|${escaped_update_root}|g" \
  "${SCRIPT_DIR}/Caddyfile.https" >"$temporary_caddy"
if [[ -n "${LEGACY_HOST}" ]]; then
  cat >>"$temporary_caddy" <<EOF

http://${LEGACY_HOST} {
  encode zstd gzip

  handle_path /collab* {
    reverse_proxy 127.0.0.1:4319
  }

  @legacy_backend path /api/* /auth/* /health /updates/*
  handle @legacy_backend {
    reverse_proxy 127.0.0.1:4318
  }

  handle {
    root * "${APP_ROOT}/apps/client/dist"
    try_files {path} /index.html
    file_server
  }

  header {
    X-Content-Type-Options nosniff
    Referrer-Policy strict-origin-when-cross-origin
    X-Frame-Options SAMEORIGIN
  }
}
EOF
fi
sudo install -m 644 "$temporary_caddy" /etc/caddy/Caddyfile
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile

sudo systemctl daemon-reload
sudo systemctl disable --now modeling-agent.service 2>/dev/null || true
sudo systemctl reset-failed qilintex.service || true
sudo systemctl enable --now qilintex.service
sudo systemctl restart qilintex.service
sudo systemctl restart caddy.service

for _ in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:4318/health >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:4318/health >/dev/null
if [[ "$environment_created" == "1" ]]; then
  printf 'TEAM_ACCESS_CODE=%s\n' "$TEAM_CODE"
else
  printf 'ENVIRONMENT=preserved\n'
fi
printf 'APP_ROOT=%s\n' "$APP_ROOT"
printf 'QILINTEX_STATUS=%s\n' "$(systemctl is-active qilintex.service)"
printf 'CADDY_STATUS=%s\n' "$(systemctl is-active caddy.service)"
