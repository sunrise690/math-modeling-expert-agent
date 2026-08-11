#!/usr/bin/env bash
set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:?请设置 PUBLIC_HOST，例如 example.com 或 203.0.113.10}"
TEAM_CODE="QT-$(openssl rand -hex 6)"
SESSION_SECRET="$(openssl rand -hex 48)"

if ! id -u qilintex >/dev/null 2>&1; then
  sudo useradd --system --home-dir /var/lib/qilintex --create-home --shell /usr/sbin/nologin qilintex
fi

sudo install -d -o qilintex -g qilintex -m 750 /var/lib/qilintex
sudo install -d -o root -g qilintex -m 750 /etc/qilintex

temporary_env="$(mktemp)"
temporary_caddy="$(mktemp)"
trap 'rm -f "$temporary_env" "$temporary_caddy"' EXIT
cat >"$temporary_env" <<EOF
NODE_ENV=production
HOME=/var/lib/qilintex
HOST=127.0.0.1
PORT=4318
COLLAB_PORT=4319
CLIENT_URL=http://${PUBLIC_HOST}
CLIENT_URLS=http://${PUBLIC_HOST}
PUBLIC_API_URL=http://${PUBLIC_HOST}
PUBLIC_COLLAB_URL=ws://${PUBLIC_HOST}/collab
SESSION_SECRET=${SESSION_SECRET}
ALLOW_DEV_LOGIN=false
TEAM_NAME=QilinTeX内部团队
TEAM_ACCESS_CODE=${TEAM_CODE}
DATA_DIR=/var/lib/qilintex
QQ_APP_ID=
QQ_APP_SECRET=
QQ_REDIRECT_URI=http://${PUBLIC_HOST}/auth/qq/callback
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_REDIRECT_URI=http://${PUBLIC_HOST}/auth/wechat/callback
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
OPENAI_CODE_INTERPRETER=true
OPENAI_IMAGE_GENERATION=true
TEX_ENGINE=latexmk
TEX_LATEXMK_ENGINE=xelatex
EOF

sudo install -o root -g qilintex -m 640 "$temporary_env" /etc/qilintex/qilintex.env
sudo install -m 644 /opt/qilintex/current/deploy/qilintex.service /etc/systemd/system/qilintex.service
sed "s/__PUBLIC_HOST__/${PUBLIC_HOST}/g" /opt/qilintex/current/deploy/Caddyfile.http >"$temporary_caddy"
sudo install -m 644 "$temporary_caddy" /etc/caddy/Caddyfile
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile

sudo systemctl daemon-reload
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
printf 'TEAM_ACCESS_CODE=%s\n' "$TEAM_CODE"
printf 'QILINTEX_STATUS=%s\n' "$(systemctl is-active qilintex.service)"
printf 'CADDY_STATUS=%s\n' "$(systemctl is-active caddy.service)"
