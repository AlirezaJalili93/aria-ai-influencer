#!/usr/bin/env bash
# ============================================================================
# اسکریپت استقرار مستقیم پروژه «آریا» از گیت (GitHub / GitLab) روی سرور لینوکس
# آدرس سرور هدف: 195.248.241.48
# ============================================================================
set -e

GIT_REPO_URL="${1:-$GIT_REPO_URL}"
APP_DIR="/opt/aria-ai-influencer"
SERVICE_NAME="aria-instagram-agent"

echo "=================================================================="
echo "🤖 راه‌اندازی پروژه مستقل ایجنت «آریا» از طریق Git روی سرور لینوکس"
echo "=================================================================="

# ۱. نصب پیش‌نیازها (git, python3, curl, ufw)
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y -qq
    apt-get install -y -qq git python3 python3-pip python3-venv curl ufw
fi

# ۲. کلون کردن یا آپدیت مخزن از گیت
if [ -d "$APP_DIR/.git" ]; then
    echo "🔄 مخزن گیت از قبل در $APP_DIR وجود دارد؛ در حال دریافت آخرین تغییرات (git pull)..."
    cd "$APP_DIR"
    if [ -n "$GIT_REPO_URL" ]; then
        git remote set-url origin "$GIT_REPO_URL"
    fi
    git fetch --all
    git reset --hard origin/main
elif [ -n "$GIT_REPO_URL" ]; then
    echo "📥 در حال کلون کردن پروژه از مخزن گیت: $GIT_REPO_URL ..."
    rm -rf "$APP_DIR"
    git clone "$GIT_REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
else
    echo "📂 کپی فایل‌های محلی پروژه به $APP_DIR ..."
    mkdir -p "$APP_DIR"
    cp -r . "$APP_DIR/"
    cd "$APP_DIR"
fi

mkdir -p "$APP_DIR/data/logs"

# ۳. ساخت فایل .env در صورت عدم وجود
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "⚙️ فایل تنظیمات اولیه در $APP_DIR/.env ساخته شد."
fi

# اگر متغیرهای محیطی در شل تعریف شده باشند، در .env جایگزین می‌شوند
if [ -n "$IG_ACCESS_TOKEN" ]; then
    sed -i "s|^IG_ACCESS_TOKEN=.*|IG_ACCESS_TOKEN="$IG_ACCESS_TOKEN"|" "$APP_DIR/.env"
fi
if [ -n "$IG_USER_ID" ]; then
    sed -i "s|^IG_USER_ID=.*|IG_USER_ID="$IG_USER_ID"|" "$APP_DIR/.env"
fi
if [ -n "$GEMINI_API_KEY" ]; then
    sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY="$GEMINI_API_KEY"|" "$APP_DIR/.env"
fi

# ۴. نصب و فعال‌سازی سرویس ۲۴/۷ در systemd
cp "$APP_DIR/systemd/aria-instagram-agent.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

# ۵. باز کردن پورت ۸۰۸۰ در فایروال
if command -v ufw >/dev/null 2>&1; then
    ufw allow 8080/tcp >/dev/null 2>&1 || true
fi

echo ""
echo "✅ پروژه «آریا» با موفقیت از گیت روی سرور مستقر و به صورت ۲۴/۷ فعال شد!"
echo "------------------------------------------------------------------"
echo "🌐 آدرس پنل و وب‌هوک روی سرور: http://195.248.241.48:8080/webhook"
echo "🔑 Verify Token وب‌هوک متا:    iran_first_ai_influencer_secret"
echo "📄 مسیر پروژه روی سرور:        $APP_DIR"
echo "🛠️ دستور آپدیت بعدی از گیت:    cd $APP_DIR && git pull && systemctl restart $SERVICE_NAME"
echo "📊 مشاهده لاگ زنده:            journalctl -u $SERVICE_NAME -f"
echo "=================================================================="
