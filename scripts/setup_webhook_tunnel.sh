#!/usr/bin/env bash
# AlmaLinux/RHEL: create a test-only HTTPS endpoint without publishing the admin API.
set -euo pipefail
umask 022
APP_DIR=/opt/aria-ai-influencer
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $(id -u) -ne 0 ]]; then echo 'Run as root.' >&2; exit 1; fi
if [[ "$SCRIPT_DIR" != "$APP_DIR/scripts" || ! -d /run/systemd/system ]]; then
  echo 'Run from /opt/aria-ai-influencer on the systemd VPS.' >&2; exit 1
fi
case "${1:-}" in
  --status) exec /usr/bin/python3 "$SCRIPT_DIR/webhook_tunnel_status.py" ;;
  --stop)
    systemctl disable --now aria-webhook-tunnel.service aria-webhook-relay.service
    echo 'Public webhook tunnel stopped. The agent/dashboard service is unchanged.'
    exit 0 ;;
  '') ;;
  *) echo 'Usage: bash scripts/setup_webhook_tunnel.sh [--status|--stop]' >&2; exit 2 ;;
esac
command -v dnf >/dev/null || { echo 'This installer targets AlmaLinux/RHEL with dnf.' >&2; exit 1; }
systemctl is-active --quiet aria-instagram-agent
cd "$APP_DIR"
aria_backend_port="$(.venv/bin/python - <<'PY'
from dotenv import dotenv_values
config = dotenv_values('.env')
if config.get('AGENT_WEBHOOK_HOST') != '127.0.0.1':
    raise SystemExit('Agent must remain bound to 127.0.0.1')
port = int(config.get('AGENT_WEBHOOK_PORT') or 8080)
if not 1 <= port <= 65535 or port == 8081:
    raise SystemExit('Invalid upstream port or collision with relay port 8081')
print(port)
PY
)"
curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:$aria_backend_port/health" >/dev/null
if ss -H -ltn '( sport = :8081 )' | read -r _; then
  systemctl is-active --quiet aria-webhook-relay || { echo 'Port 8081 is occupied by another service.' >&2; exit 1; }
fi
# Only install the Cloudflare package when missing. Preserve any existing tunnel/service.
if ! command -v cloudflared >/dev/null; then
  aria_repo_file="$(mktemp)"
  trap 'rm -f "$aria_repo_file"' EXIT
  curl --fail --silent --show-error --location --max-time 30 \
    https://pkg.cloudflare.com/cloudflared.repo -o "$aria_repo_file"
  if [[ -f /etc/yum.repos.d/cloudflared.repo ]]; then
    cp -a /etc/yum.repos.d/cloudflared.repo "/root/cloudflared.repo.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  install -m 644 "$aria_repo_file" /etc/yum.repos.d/cloudflared.repo
  dnf install -y cloudflared
fi
aria_cloudflared="$(command -v cloudflared)"
[[ "$aria_cloudflared" =~ ^/[a-zA-Z0-9_./-]+$ ]] || { echo 'Unexpected cloudflared executable path.' >&2; exit 1; }
aria_tunnel_backup="$(mktemp -d /root/aria-webhook-backup-XXXXXXXX)"
chmod 700 "$aria_tunnel_backup"
for aria_unit in aria-webhook-relay.service aria-webhook-tunnel.service; do
  [[ ! -f /etc/systemd/system/$aria_unit ]] || cp -a "/etc/systemd/system/$aria_unit" "$aria_tunnel_backup/"
done
[[ ! -d /etc/aria-webhook ]] || cp -a /etc/aria-webhook "$aria_tunnel_backup/"
[[ ! -d /usr/local/lib/aria-webhook ]] || cp -a /usr/local/lib/aria-webhook "$aria_tunnel_backup/"
printf 'Tunnel configuration backup: %s\n' "$aria_tunnel_backup"
# Install a separate copy: an app Git rollback cannot remove this gateway.
install -d -m 755 /usr/local/lib/aria-webhook /etc/aria-webhook
install -m 644 scripts/webhook_relay.py /usr/local/lib/aria-webhook/webhook_relay.py
# Explicit isolated config: never inherit another cloudflared account/config.
printf 'url: http://127.0.0.1:8081\n' > /etc/aria-webhook/cloudflared.yml
chmod 644 /etc/aria-webhook/cloudflared.yml
cat > /etc/systemd/system/aria-webhook-relay.service <<UNIT
[Unit]
Description=Aria webhook-only loopback gateway
After=network.target aria-instagram-agent.service

[Service]
DynamicUser=yes
ExecStart=/usr/bin/python3 /usr/local/lib/aria-webhook/webhook_relay.py --port 8081 --upstream-port $aria_backend_port
Restart=always
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/aria-webhook-tunnel.service <<UNIT
[Unit]
Description=Aria temporary HTTPS webhook tunnel (URL changes after restart)
After=network-online.target aria-webhook-relay.service
Wants=network-online.target aria-webhook-relay.service

[Service]
DynamicUser=yes
ExecStart=$aria_cloudflared tunnel --config /etc/aria-webhook/cloudflared.yml --no-autoupdate --protocol http2 --url http://127.0.0.1:8081
Restart=always
RestartSec=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
chmod 644 /etc/systemd/system/aria-webhook-{relay,tunnel}.service
systemctl daemon-reload
systemctl enable aria-webhook-relay.service aria-webhook-tunnel.service
systemctl restart aria-webhook-relay.service
# Check the actual upstream and route isolation before starting the public tunnel.
/usr/bin/python3 - <<'PY'
import importlib.util, time
spec = importlib.util.spec_from_file_location('status', 'scripts/webhook_tunnel_status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)
for attempt in range(20):
    try:
        status.check_routes('http://127.0.0.1:8081')
        break
    except (OSError, RuntimeError):
        time.sleep(0.25)
else:
    raise SystemExit('Local gateway failed checks; public tunnel was not started.')
PY
# Preserve an already running tunnel and its URL when rerunning this installer.
systemctl start aria-webhook-tunnel.service
if ! /usr/bin/python3 scripts/webhook_tunnel_status.py --wait 45; then
  echo 'Services installed; public connectivity is not verified. Rerun with --status after inspecting the tunnel journal.' >&2
  exit 1
fi
echo 'Meta App Secret, Instagram access and webhook subscription still require configuration in Meta.'
echo 'No .env/API key/database/firewall changes were made.'
