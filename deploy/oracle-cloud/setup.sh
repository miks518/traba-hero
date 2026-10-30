#!/usr/bin/env bash
#
# Trabahero backend — one-shot bootstrap for a fresh Oracle Cloud (OCI) Ubuntu VM.
#
# Target OS: Ubuntu 22.04 or 24.04 (apt). Run as a user with sudo:
#     sudo bash setup.sh
#
# What it does:
#   1. Installs python3, venv, git, and Caddy (auto-HTTPS reverse proxy)
#   2. Creates a `trabahero` service user
#   3. Clones the repo to /opt/trabahero
#   4. Creates a venv and installs backend/requirements.txt
#   5. Installs the systemd unit and Caddyfile
#   6. Leaves you to fill in /opt/trabahero/backend/.env, then start services
#
set -euo pipefail

REPO_URL="https://github.com/miks518/traba-hero.git"
APP_DIR="/opt/trabahero"
APP_USER="trabahero"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash setup.sh" >&2
  exit 1
fi

echo "==> Installing system packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip git curl debian-keyring debian-archive-keyring apt-transport-https

echo "==> Installing Caddy (official repo)"
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y caddy
fi

echo "==> Creating service user ${APP_USER}"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"

echo "==> Cloning ${REPO_URL} -> ${APP_DIR}"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" pull --ff-only
else
  git clone "${REPO_URL}" "${APP_DIR}"
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "==> Creating virtualenv and installing requirements"
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/backend/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/backend/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/backend/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

echo "==> Installing systemd unit"
cp "${APP_DIR}/deploy/oracle-cloud/trabahero.service" /etc/systemd/system/trabahero.service
systemctl daemon-reload

echo "==> Installing Caddyfile (EDIT THE HOSTNAME!)"
if [[ ! -f /etc/caddy/Caddyfile.bak ]]; then
  cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak 2>/dev/null || true
fi
cp "${APP_DIR}/deploy/oracle-cloud/Caddyfile" /etc/caddy/Caddyfile
echo "   -> /etc/caddy/Caddyfile now points at a placeholder host."
echo "   -> Edit it to your domain or <PUBLIC_IP>.sslip.io, then: systemctl reload caddy"

echo "==> Ensuring backend/.env exists"
if [[ ! -f "${APP_DIR}/backend/.env" ]]; then
  cp "${APP_DIR}/backend/.env.example" "${APP_DIR}/backend/.env"
  chown "${APP_USER}:${APP_USER}" "${APP_DIR}/backend/.env"
  chmod 600 "${APP_DIR}/backend/.env"
  echo "   -> Fill in secrets in ${APP_DIR}/backend/.env before starting."
fi

cat <<EOF

============================================================
Setup complete. Remaining manual steps:

1. Edit ${APP_DIR}/backend/.env  (at minimum set):
     AI_API_KEY=...
     AI_API_URL=https://openrouter.ai/api/v1
     MODEL_NAME=<a VISION model id>
     TAVILY_API_KEY=...
     CORS_ALLOWED_ORIGINS=chrome-extension://hdmdhiojgdoomcjfhbkidbhkifmokkop
     TRUSTED_PROXIES=127.0.0.1/32
   then:  chmod 600 ${APP_DIR}/backend/.env

2. Point Caddy at your host:
     nano /etc/caddy/Caddyfile      # set the hostname
     systemctl reload caddy

3. Start the backend:
     systemctl enable --now trabahero
     systemctl status trabahero

4. Open the firewalls (BOTH needed):
   a) OCI Console -> VCN -> Security List -> add Ingress rules:
        TCP 80  0.0.0.0/0
        TCP 443 0.0.0.0/0
   b) On the instance (Oracle images ship restrictive iptables):
        See deploy/oracle-cloud/README.md -> "Open the instance firewall".

5. Verify:
     curl https://<your-host>/health       -> {"status":"ok"}
============================================================
EOF
