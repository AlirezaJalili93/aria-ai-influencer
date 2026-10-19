#!/usr/bin/env bash
# Back up the complete installation before checking out a Git revision.
set -euo pipefail
umask 022
cd /opt/aria-ai-influencer
if [[ $(id -u) -ne 0 ]]; then echo 'Run as root.' >&2; exit 1; fi
aria_revision="${1:-codex/prepare-server-deployment}"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'STOP: tracked local changes found; nothing overwritten.' >&2
  git status --short
  exit 1
fi
git fetch origin "$aria_revision"
aria_target="$(git rev-parse FETCH_HEAD)"
aria_previous="$(git rev-parse HEAD)"
aria_backup="$(mktemp -d /root/aria-backup-XXXXXXXX)"
chmod 700 "$aria_backup"
printf '%s\n' "$aria_previous" > "$aria_backup/previous-revision"
printf '%s\n' "$aria_target" > "$aria_backup/target-revision"
aria_was_active=0
systemctl is-active --quiet aria-instagram-agent && aria_was_active=1
cp -a /etc/systemd/system/aria-instagram-agent.service "$aria_backup/" 2>/dev/null || true
[[ ! -f .env ]] || cp -a .env "$aria_backup/"
aria_stopped=0
rollback() {
  aria_rc=$?
  trap - ERR
  if [[ "$aria_stopped" == 1 ]]; then
    echo "Update failed. Returning code/service/config to $aria_previous. New database records are preserved." >&2
    systemctl stop aria-instagram-agent || true
    git checkout --detach "$aria_previous" || true
    [[ ! -f "$aria_backup/.env" ]] || cp -a "$aria_backup/.env" .env
    [[ ! -f "$aria_backup/aria-instagram-agent.service" ]] || cp -a "$aria_backup/aria-instagram-agent.service" /etc/systemd/system/
    systemctl daemon-reload || true
    if [[ "$aria_was_active" == 1 ]]; then systemctl start aria-instagram-agent || true; fi
  fi
  echo "Backup: $aria_backup" >&2
  exit "$aria_rc"
}
trap rollback ERR
systemctl stop aria-instagram-agent
aria_stopped=1
# Service is stopped: DB, WAL, media, config and unknown local files form one backup.
tar --exclude=.git --exclude=.venv -czf "$aria_backup/app.tar.gz" .
chmod 600 "$aria_backup/app.tar.gz"
git checkout --detach "$aria_target"
bash scripts/server_git_deploy.sh
.venv/bin/python scripts/verify_transfer.py
trap - ERR
printf '\nInstalled Git revision: %s\nComplete backup: %s\n' "$aria_target" "$aria_backup"
