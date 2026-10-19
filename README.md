# 🤖 پروژه مستقل ایجنت «آریا» (Aria AI Influencer)

**اولین اینفلوئنسر هوش مصنوعی ایران — متصل به Meta Instagram Graph API v21.0 + روتر چند هوش مصنوعی (Multi-AI Router)**

این مخزن یک پروژه کامل، مستقل و آماده استقرار روی سرور لینوکس (`195.248.241.48`) است که تمامی اجزای ایجنت «آریا» شامل هسته پایتون، وب‌هوک ۲۴/۷ دایرکت و کامنت، زمان‌بندی استوری و ریلز، گاوصندوق مدیریت توکن‌های هوش مصنوعی، پنل تحت وب فارسی (RTL با فونت وزیرمتن) و پایپ‌لاین CI/CD گیت‌هاب را در یک ساختار استاندارد گردآوری کرده است.

---

## 📁 ساختار پوشه‌ها و فایل‌های پروژه

```text
aria-ai-influencer/
├── instagram_ai_agent.py              # فایل اجرایی اصلی ایجنت و سرور وب‌هوک ۲۴/۷
├── aria_ai_influencer_live.html       # پنل وب تعاملی و شبیه‌ساز زنده پیج اینستاگرام
├── src/
│   └── instagram_ai_agent.py          # سورس ماژولار هسته ایجنت
├── web/
│   └── index.html                     # نسخه وب پنل مدیریت آنلاین آریا
├── docs/
│   └── ai_influencer_playbook.md      # پلی‌بوک استراتژی محتوا و معماری فنی آریا
├── scripts/
│   ├── push_and_deploy.ps1            # اسکریپت ویندوز (PowerShell): ارسال به گیت + نصب روی سرور
│   ├── push_and_deploy.sh             # اسکریپت لینوکس/مک (Bash): ارسال به گیت + نصب روی سرور
│   ├── server_git_deploy.sh           # اسکریپت نصب و آپدیت مستقیم از گیت در داخل سرور لینوکس
│   └── deploy_aria_instagram_24_7.sh  # اسکریپت نصب مستقیم سرویس systemd
├── systemd/
│   └── aria-instagram-agent.service   # فایل سرویس ۲۴/۷ لینوکس (systemd)
├── .github/workflows/
│   └── deploy.yml                     # استقرار خودکار (CI/CD) روی سرور به محض هر git push
├── Dockerfile                         # فایل ساخت ایمیج داکر
├── docker-compose.yml                 # اجرای کانتینری ۲۴/۷ با Docker Compose
├── .env.example                       # الگوی متغیرهای محیطی و توکن‌ها (بدون لو رفتن کلیدها در گیت)
├── .gitignore                         # محافظت از فایل‌های حساس (.env و کلیدهای API)
└── requirements.txt                   # وابستگی‌های پایتون
```

---

## 🚀 راهنمای گام‌به‌گام: اول قرار دادن روی Git و سپس استقرار روی سرور

این پوشه از قبل با `git init` مقداردهی شده و **کامیت اولیه (Initial Commit)** روی شاخه `main` در آن ثبت شده است.

### مرحله ۱: قرار دادن پروژه روی GitHub یا GitLab

۱. در اکانت GitHub یا GitLab خود یک مخزن (Repository) جدید و خالی به نام `aria-ai-influencer` بسازید (بدون تیک زدن README یا .gitignore).
۲. فایل زیپ پروژه را روی سیستم خود استخراج (Extract) کنید و در ترمینال یا PowerShell داخل پوشه پروژه این ۳ خط را اجرا کنید:

```bash
git remote add origin https://github.com/YOUR_USERNAME/aria-ai-influencer.git
git branch -M main
git push -u origin main
```

---

### مرحله ۲: انتقال از Git به سرور (`195.248.241.48`) و اجرای ۲۴/۷

حالا که پروژه روی گیت قرار گرفت، وارد سرور لینوکس خود شوید و با یک دستور، پروژه را مستقیم از گیت کلون و سرویس ۲۴/۷ را فعال کنید:

```bash
ssh root@195.248.241.48
```

سپس داخل سرور این دستور را اجرا کنید (آدرس گیت خود را جایگزین کنید):

```bash
git clone https://github.com/YOUR_USERNAME/aria-ai-influencer.git /opt/aria-ai-influencer && cd /opt/aria-ai-influencer && chmod +x scripts/*.sh && ./scripts/server_git_deploy.sh
```

> **💡 نکته طلایی برای تنظیم توکن‌ها روی سرور:**
> بعد از کلون شدن پروژه در مسیر `/opt/aria-ai-influencer`، فایل `/opt/aria-ai-influencer/.env` را باز کنید (`nano /opt/aria-ai-influencer/.env`)، توکن اینستاگرام (`IG_ACCESS_TOKEN`)، شناسه پیج (`IG_USER_ID`) و کلید هوش مصنوعی (`GEMINI_API_KEY` یا کلیدهای دیگر) را وارد کنید و سرویس را ری‌استارت نمایید:
> ```bash
> systemctl restart aria-instagram-agent
> ```

---

### ⚡ روش تک‌فرمانی (هم Push به گیت و هم نصب روی سرور با یک دستور از ویندوز)

اگر روی ویندوز هستید، کافی است در PowerShell داخل پوشه پروژه دستور زیر را اجرا کنید تا هم به گیت Push شود و هم از طریق SSH روی سرور `195.248.241.48` از گیت کلون و فعال گردد:

```powershell
.\scripts\push_and_deploy.ps1 -GitRepoUrl "https://github.com/YOUR_USERNAME/aria-ai-influencer.git"
```

---

### 🔄 آپدیت‌های بعدی پروژه (CI/CD خودکار با GitHub Actions)

فایل `.github/workflows/deploy.yml` در پروژه قرار داده شده است. اگر در تنظیمات مخزن گیت‌هاب خود (`Settings -> Secrets and variables -> Actions`) مقادیر زیر را ثبت کنید:
- `SERVER_HOST`: `195.248.241.48`
- `SERVER_USER`: `root`
- `SERVER_PASSWORD`: رمز عبور سرور شما (یا `SERVER_SSH_KEY`)

از این پس هر بار که روی سیستم خود کد را تغییر دهید و `git push` بزنید، گیت‌هاب به صورت خودکار وارد سرور `195.248.241.48` می‌شود، دستور `git pull` را اجرا می‌کند و سرویس ۲۴/۷ آریا را بدون یک ثانیه قطعی آپدیت و ری‌استارت می‌کند!
