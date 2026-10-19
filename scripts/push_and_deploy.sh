#!/usr/bin/env bash
# ============================================================================
# اسکریپت خودکار دو مرحله‌ای (ویژه Linux / macOS / Git Bash):
# ۱) ارسال پروژه «آریا» به مخزن گیت (GitHub / GitLab)
# ۲) اتصال به سرور 195.248.241.48 و استقرار مستقیم از روی مخزن گیت
# ============================================================================
set -e

GIT_REPO_URL="$1"
SERVER_IP="${2:-195.248.241.48}"
SERVER_USER="${3:-root}"

if [ -z "$GIT_REPO_URL" ]; then
    echo "⚠️ لطفاً آدرس مخزن گیت خود را وارد کنید:"
    echo "مثال: ./scripts/push_and_deploy.sh https://github.com/USERNAME/aria-ai-influencer.git"
    exit 1
fi

echo "🚀 گام ۱: ارسال پروژه مستقل «آریا» به مخزن گیت ($GIT_REPO_URL)..."
if [ ! -d ".git" ]; then
    git init -b main
fi

git add .
git commit -m "chore: update Aria AI Influencer standalone project" || true

if git remote | grep -q "^origin$"; then
    git remote set-url origin "$GIT_REPO_URL"
else
    git remote add origin "$GIT_REPO_URL"
fi

git branch -M main
git push -u origin main

echo "🖥️ گام ۲: اتصال به سرور $SERVER_USER@$SERVER_IP و استقرار مستقیم از مخزن گیت..."
ssh -t "${SERVER_USER}@${SERVER_IP}" "
    export GIT_REPO_URL='${GIT_REPO_URL}'
    if [ -d /opt/aria-ai-influencer/.git ]; then
        cd /opt/aria-ai-influencer && git pull origin main
    else
        rm -rf /opt/aria-ai-influencer && git clone '${GIT_REPO_URL}' /opt/aria-ai-influencer
    fi
    cd /opt/aria-ai-influencer
    sed -i 's/$//' scripts/*.sh
    chmod +x scripts/*.sh
    ./scripts/server_git_deploy.sh '${GIT_REPO_URL}'
"
