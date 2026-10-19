#!/usr/bin/env bash
# Install the checked-out revision; never reset Git or change the firewall.
set -euo pipefail
umask 022
APP_DIR="/opt/aria-ai-influencer"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="aria-instagram-agent"

if [[ "${1:-}" == "--check" ]]; then
  cat /etc/os-release
  python3 --version
  command -v systemctl || true
  df -h /opt
  if command -v ss >/dev/null; then ss -ltn '( sport = :8080 )'; fi
  systemctl is-active "$SERVICE_NAME" || true
  printf 'Source: %s\n' "$SOURCE_DIR"
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo 'Usage: bash scripts/server_git_deploy.sh [--check]' >&2
  exit 2
fi
if [[ $(id -u) -ne 0 ]]; then
  echo 'Run this installer as root (or sudo bash scripts/server_git_deploy.sh).' >&2
  exit 1
fi
if [[ "$SOURCE_DIR" != "$APP_DIR" ]]; then
  echo "Checkout must be at $APP_DIR. No files were changed." >&2
  exit 1
fi
if [[ ! -d /run/systemd/system ]]; then
  echo 'A running systemd host is required. Use Docker Compose in containers.' >&2
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,9), "Python 3.9+ is required"'
# Refuse an unrelated listener before touching an existing installation.
if command -v ss >/dev/null && ss -H -ltn '( sport = :8080 )' | read -r _; then
  if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo 'Port 8080 is already occupied. Inspect the listener before installing.' >&2
    exit 1
  fi
fi
if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
  if command -v apt-get >/dev/null; then
    apt-get update
    apt-get install -y python3-venv
  else
    echo 'Install the Python venv package for your distribution first.' >&2
    exit 1
  fi
fi
cd "$APP_DIR"
# Git checkout may have run under umask 077. The service account needs to
# traverse the app directory and read this entrypoint; secrets stay private.
chmod 0755 "$APP_DIR"
chmod 0644 "$APP_DIR/instagram_ai_agent.py"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import cv2, numpy, PIL'
.venv/bin/python instagram_ai_agent.py --help >/dev/null

if ! id aria-agent >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin aria-agent
fi
install -d -m 700 -o aria-agent -g aria-agent "$APP_DIR/data"
# Existing config is preserved, with a root-only backup before filling defaults.
if [[ -f .env ]]; then
  install -m 600 .env ".env.backup.$(date -u +%Y%m%dT%H%M%SZ)"
else
  install -m 600 .env.example .env
fi
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
from dotenv import dotenv_values
p = Path('.env')
values = dotenv_values(p)
# Correct names from the previous sample. Preserve all real API keys.
updates = {
    'AGENT_DB_PATH': str(Path.cwd() / 'data/instagram_agent_state.db'),
    'AGENT_WEBHOOK_HOST': '127.0.0.1',
    'AGENT_WEBHOOK_PORT': values.get('AGENT_WEBHOOK_PORT') or '8080',
    'IG_GRAPH_VERSION': values.get('IG_GRAPH_VERSION') or values.get('IG_GRAPH_API_VERSION') or 'v21.0',
    'DEFAULT_DAILY_TOKEN_LIMIT': values.get('DEFAULT_DAILY_TOKEN_LIMIT') or values.get('DAILY_TOKEN_BUDGET') or '500000',
    'TZ': 'Asia/Tehran',
}
if not values.get('IG_WEBHOOK_VERIFY_TOKEN') or values.get('IG_WEBHOOK_VERIFY_TOKEN') == 'iran_first_ai_influencer_secret':
    updates['IG_WEBHOOK_VERIFY_TOKEN'] = secrets.token_urlsafe(32)
for k, v in [('IG_ACCESS_TOKEN','EAA_YOUR_META_GRAPH_API_ACCESS_TOKEN'), ('IG_USER_ID','17841400000000000'), ('GEMINI_API_KEY','AIzaSy_YOUR_GEMINI_KEY')]:
    if values.get(k) == v:
        updates[k] = ''
lines = p.read_text().splitlines()
lines = [line for line in lines if line.split('=', 1)[0].strip() not in updates]
lines += [f'{key}="{value}"' for key, value in updates.items()]
p.write_text('\n'.join(lines) + '\n')
PY
chown root:aria-agent .env
chmod 640 .env
# Preserve state from the previous installers before changing the DB path.
.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3
target = Path('data/instagram_agent_state.db')
old_paths = [Path('/tmp/instagram_agent_state.db'), Path('/opt/aria_instagram_agent/data/instagram_agent_state.db')]
sources = [p for p in old_paths if p.is_file()]
if not target.exists() and len(sources) > 1:
    raise SystemExit('Multiple legacy databases found. Select and migrate the active database before installing.')
if not target.exists() and sources:
    with sqlite3.connect(str(sources[0])) as source, sqlite3.connect(str(target)) as dest:
        source.backup(dest)
    print('Legacy database copied using SQLite backup; original preserved.')
PY
chown -R aria-agent:aria-agent "$APP_DIR/data"
chmod 700 "$APP_DIR/data"
if [[ -f /etc/systemd/system/$SERVICE_NAME.service ]]; then
  install -m 600 "/etc/systemd/system/$SERVICE_NAME.service" ".service.backup.$(date -u +%Y%m%dT%H%M%SZ)"
fi
install -m 644 systemd/aria-instagram-agent.service "/etc/systemd/system/$SERVICE_NAME.service"
runuser -u aria-agent -- "$APP_DIR/.venv/bin/python" "$APP_DIR/instagram_ai_agent.py" --help >/dev/null
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
.venv/bin/python - <<'PY'
import json, subprocess, time, urllib.request
from dotenv import dotenv_values
port = int(dotenv_values('.env').get('AGENT_WEBHOOK_PORT') or 8080)
for attempt in range(20):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
            status = json.load(r)
        subprocess.run(['systemctl', 'is-active', '--quiet', 'aria-instagram-agent'], check=True)
        if status.get('status') != 'ONLINE':
            raise ValueError('Unexpected health response')
        print('Local HTTP service is healthy. Instagram/API credentials still need live verification.')
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Health check failed. Run: journalctl -u aria-instagram-agent -n 50 --no-pager')
PY
systemctl --no-pager --full status "$SERVICE_NAME"
printf '\nConfiguration: %s/.env\nLogs: journalctl -u %s -f\n' "$APP_DIR" "$SERVICE_NAME"
echo 'The admin API listens locally. Do not publish port 8080; see docs/server_deployment.md.'
