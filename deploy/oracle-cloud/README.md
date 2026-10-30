# Deploying the Trabahero backend on Oracle Cloud Free Tier

Always-Free, always-on hosting for the FastAPI backend. This is a raw VM
(IaaS), so unlike Railway there is OS setup — but it costs $0 and never sleeps.

Files here:
- `setup.sh` — bootstraps a fresh Ubuntu VM (packages, user, clone, venv, systemd, Caddy)
- `trabahero.service` — systemd unit
- `Caddyfile` — reverse proxy with automatic HTTPS

---

## 1. Create the VM

OCI Console → **Compute → Instances → Create instance**.

| Setting | Value |
|---|---|
| Image | **Ubuntu 22.04** or **24.04** |
| Shape | **VM.Standard.A1.Flex** (Ampere ARM, Always Free, up to 4 OCPU / 24 GB) |
| | or **VM.Standard.E2.1.Micro** (AMD, Always Free, 1 GB) |
| Networking | Assign a **public IPv4** address |
| SSH keys | Upload your public key (or let OCI generate one and download the private key) |

> The ARM Ampere shape may report **"Out of host capacity"** in busy regions.
> Retry later, pick another AD (availability domain), or fall back to the AMD
> micro shape — 1 GB is enough for this backend.

Note the instance's **public IP** and the SSH username (Ubuntu images default to
`ubuntu`).

## 2. Open the VCN Security List (first firewall)

OCI Console → **Networking → Virtual Cloud Networks → your VCN → Security Lists
→ Default Security List → Add Ingress Rules**:

| Source | Protocol | Dest port |
|---|---|---|
| `0.0.0.0/0` | TCP | **80** |
| `0.0.0.0/0` | TCP | **443** |

## 3. SSH in and run the bootstrap

```bash
ssh ubuntu@<PUBLIC_IP>

# get the repo (or scp this repo up); the script clones it itself:
sudo apt-get update -y && sudo apt-get install -y git
git clone https://github.com/miks518/traba-hero.git /tmp/traba-hero
sudo bash /tmp/traba-hero/deploy/oracle-cloud/setup.sh
```

`setup.sh` installs packages + Caddy, creates the `trabahero` user, clones to
`/opt/trabahero`, builds the venv, installs the systemd unit and Caddyfile.

## 4. Fill in secrets

```bash
sudo nano /opt/trabahero/backend/.env
```

Set at least:

```ini
AI_API_KEY=<your provider key>
AI_API_URL=https://openrouter.ai/api/v1
MODEL_NAME=<a VISION-capable model id>
TAVILY_API_KEY=<your Tavily key>
CORS_ALLOWED_ORIGINS=chrome-extension://hdmdhiojgdoomcjfhbkidbhkifmokkop
TRUSTED_PROXIES=127.0.0.1/32
```

- **`TRUSTED_PROXIES=127.0.0.1/32`** — Caddy proxies from loopback, so this is
  the only hop. Without it the rate limiter sees one shared bucket.
- **`CORS_ALLOWED_ORIGINS`** must equal the extension's published ID.

```bash
sudo chmod 600 /opt/trabahero/backend/.env
```

## 5. Point Caddy at your host (HTTPS)

No domain? Use `sslip.io`, which resolves `<anything>.<ip>.sslip.io` to the IP:

```bash
sudo sed -i "s/203.0.113.10/<PUBLIC_IP>/" /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy fetches a Let's Encrypt cert automatically.

## 6. Open the instance firewall (second firewall)

Oracle's Ubuntu images ship iptables rules that block everything but SSH. Add
80/443:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

(If the image uses `ufw` instead: `sudo ufw allow 80,443/tcp`.)

## 7. Start the backend and verify

```bash
sudo systemctl enable --now trabahero
sudo systemctl status trabahero --no-pager

curl https://<PUBLIC_IP>.sslip.io/health     # -> {"status":"ok"}
```

Logs: `journalctl -u trabahero -f`

## 8. Point the extension at it

Easiest: open the extension's **Settings** page and set the Backend URL to
`https://<PUBLIC_IP>.sslip.io` — stored in `chrome.storage.local`, no rebuild.

Or bake it in: set `WXT_API_BASE=https://<PUBLIC_IP>.sslip.io` in the repo
`.env`, then `npm run build` and re-upload.

---

## Operations

```bash
# Update after a git push:
sudo -u trabahero git -C /opt/trabahero pull --ff-only
sudo -u trabahero /opt/trabahero/backend/.venv/bin/pip install -r /opt/trabahero/backend/requirements.txt
sudo systemctl restart trabahero
```

**Notes**
- Do **not** expose port 8010 publicly — Caddy is the only entry point, and the
  service binds loopback on purpose.
- Oracle may reclaim **idle** Always-Free instances. A continuously running web
  service counts as active, so this is generally safe.
- Rolling your own TLS means you own renewals — Caddy handles them, but keep
  ports 80 and 443 open or renewal will fail.
