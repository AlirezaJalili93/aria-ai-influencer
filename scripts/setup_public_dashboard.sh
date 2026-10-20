#!/usr/bin/env bash
# Stable IP HTTPS frontend, separate from the private agent and temporary tunnel.
set -euo pipefail
umask 022
APP_DIR=/opt/aria-ai-influencer
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
aria_bin=/usr/local/bin/aria-dashboard-caddy
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
[[ "$SCRIPT_DIR" == "$APP_DIR/scripts" && -d /run/systemd/system ]] || { echo 'Run from the systemd VPS checkout at /opt/aria-ai-influencer.' >&2; exit 1; }
case "${1:-}" in
  --status) exec /usr/bin/python3 "$SCRIPT_DIR/public_dashboard.py" status ;;
  --stop) systemctl disable --now aria-dashboard; exit 0 ;;
esac
aria_ip="${1:-195.248.241.48}"
aria_reset=()
if [[ "${2:-}" == --reset-password ]]; then aria_reset=(--reset-password); elif [[ $# -gt 1 ]]; then echo 'Usage: setup_public_dashboard.sh [PUBLIC_IP [--reset-password]|--status|--stop]' >&2; exit 2; fi
/usr/bin/python3 - "$aria_ip" <<'PY'
import ipaddress,sys
if not ipaddress.IPv4Address(sys.argv[1]).is_global: raise SystemExit('Public IPv4 required')
PY
systemctl is-active --quiet aria-instagram-agent
systemctl is-active --quiet aria-webhook-relay
# Do not replace another web server or an unrelated listener.
if ss -H -ltn '( sport = :80 or sport = :443 )' | read -r _; then
  systemctl is-active --quiet aria-dashboard || { echo 'STOP: ports 80/443 are occupied. No web server configuration was replaced.' >&2; ss -ltnp '( sport = :80 or sport = :443 )'; exit 1; }
  for aria_listener in $(ss -H -ltnp '( sport = :80 or sport = :443 )' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u); do
    if ! grep -q '/aria-dashboard.service' "/proc/$aria_listener/cgroup"; then
      echo 'STOP: an unrelated process also listens on ports 80/443.' >&2; exit 1
    fi
  done
fi
cd "$APP_DIR"
aria_backend_port="$(.venv/bin/python - <<'PY'
from dotenv import dotenv_values
c=dotenv_values('.env')
if c.get('AGENT_WEBHOOK_HOST')!='127.0.0.1': raise SystemExit('Agent must remain on loopback')
p=int(c.get('AGENT_WEBHOOK_PORT') or 8080)
if not 1<=p<=65535 or p in (80,443,8081): raise SystemExit('Invalid upstream port')
print(p)
PY
)"
curl -fsS --max-time 5 "http://127.0.0.1:$aria_backend_port/health" >/dev/null
case "$(uname -m)" in
  x86_64) aria_arch=amd64; aria_sha=727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b ;;
  aarch64) aria_arch=arm64; aria_sha=d8fc6d179a5d283028a472a5618564f6ad8a86fed513e64f032b3b0b7cc45e42 ;;
  *) echo 'Unsupported architecture' >&2; exit 1 ;;
esac
aria_temp="$(mktemp -d)"
trap 'rm -rf -- "$aria_temp"' EXIT
aria_backup="$(mktemp -d /root/aria-dashboard-backup-XXXXXXXX)"
chmod 700 "$aria_backup"
[[ ! -d /etc/aria-dashboard ]] || cp -a /etc/aria-dashboard "$aria_backup/config"
[[ ! -f "$aria_bin" ]] || cp -a "$aria_bin" "$aria_backup/binary"
[[ ! -f /etc/systemd/system/aria-dashboard.service ]] || cp -a /etc/systemd/system/aria-dashboard.service "$aria_backup/"
printf 'Frontend backup: %s\n' "$aria_backup"
if [[ ! -x "$aria_bin" ]] || ! "$aria_bin" version | grep -q '^v2\.11\.7 '; then
  curl --fail --silent --show-error --location --retry 2 --max-time 120 \
    "https://github.com/caddyserver/caddy/releases/download/v2.11.7/caddy_2.11.7_linux_$aria_arch.tar.gz" -o "$aria_temp/caddy.tar.gz"
  printf '%s  %s\n' "$aria_sha" "$aria_temp/caddy.tar.gz" | sha256sum -c -
  tar -xzf "$aria_temp/caddy.tar.gz" -C "$aria_temp" caddy
  install -d -m 755 /usr/local/bin
  install -m 755 "$aria_temp/caddy" "$aria_bin.new"
  mv -f "$aria_bin.new" "$aria_bin"
fi
if ! id aria-dashboard >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/aria-dashboard --shell /usr/sbin/nologin aria-dashboard
fi
install -d -m 750 -o root -g aria-dashboard /etc/aria-dashboard
install -d -m 700 -o aria-dashboard -g aria-dashboard /var/lib/aria-dashboard
/usr/bin/python3 scripts/public_dashboard.py configure --ip "$aria_ip" --upstream-port "$aria_backend_port" --caddy "$aria_bin" "${aria_reset[@]}"
chown root:aria-dashboard /etc/aria-dashboard/Caddyfile /etc/aria-dashboard/settings.json
chmod 640 /etc/aria-dashboard/Caddyfile /etc/aria-dashboard/settings.json
cat > /etc/systemd/system/aria-dashboard.service <<'UNIT'
[Unit]
Description=Aria password-protected public HTTPS dashboard
After=network-online.target aria-instagram-agent.service aria-webhook-relay.service
Wants=network-online.target

[Service]
User=aria-dashboard
Group=aria-dashboard
WorkingDirectory=/var/lib/aria-dashboard
Environment=XDG_DATA_HOME=/var/lib/aria-dashboard/data
Environment=XDG_CONFIG_HOME=/var/lib/aria-dashboard/config
ExecStart=/usr/local/bin/aria-dashboard-caddy run --config /etc/aria-dashboard/Caddyfile --adapter caddyfile
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/aria-dashboard
UMask=0077
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
chmod 644 /etc/systemd/system/aria-dashboard.service
# Only add web services to the public interface's active zone; never reload or flush rules.
if command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
  aria_iface="$(ip -4 route show default | awk '/default/ {for(i=1;i<=NF;i++) if($i=="dev") {print $(i+1); exit}}')"
  aria_zone="$(firewall-cmd --get-zone-of-interface="$aria_iface" 2>/dev/null || true)"
  if [[ -z "$aria_zone" || "$aria_zone" == 'no zone' ]]; then aria_zone="$(firewall-cmd --get-default-zone)"; fi
  for aria_web_service in http https; do
    if ! firewall-cmd --zone="$aria_zone" --query-service="$aria_web_service" >/dev/null; then
      firewall-cmd --zone="$aria_zone" --add-service="$aria_web_service"
      printf 'runtime %s %s\n' "$aria_zone" "$aria_web_service" >> "$aria_backup/added-firewall-services"
    fi
    if ! firewall-cmd --permanent --zone="$aria_zone" --query-service="$aria_web_service" >/dev/null; then
      firewall-cmd --permanent --zone="$aria_zone" --add-service="$aria_web_service"
      printf 'permanent %s %s\n' "$aria_zone" "$aria_web_service" >> "$aria_backup/added-firewall-services"
    fi
  done
fi
systemctl daemon-reload
systemctl enable aria-dashboard
systemctl restart aria-dashboard
/usr/bin/python3 scripts/public_dashboard.py status --wait 50
echo 'The core app and existing webhook tunnel were not restarted. Open the URL from another device and sign in.'
