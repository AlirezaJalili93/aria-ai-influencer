<#
.SYNOPSIS
اسکریپت خودکار دو مرحله‌ای:
۱) ارسال پروژه ایجنت «آریا» به مخزن گیت (GitHub / GitLab)
۲) اتصال به سرور 195.248.241.48 و کلون/آپدیت مستقیم پروژه از گیت روی سرور به صورت ۲۴/۷
#>

param(
    [Parameter(Mandatory=$true, HelpMessage="آدرس مخزن گیت خود را وارد کنید (مثلاً https://github.com/USERNAME/aria-ai-influencer.git)")]
    [string]$GitRepoUrl,

    [string]$ServerIp = "195.248.241.48",
    [string]$ServerUser = "root",
    [string]$IgAccessToken = "",
    [string]$IgUserId = "",
    [string]$GeminiApiKey = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "🚀 گام ۱: آماده‌سازی و ارسال پروژه «آریا» به مخزن Git..." -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    git init -b main
}

git add .
git status --short
git commit -m "chore: update Aria AI Influencer standalone project" 2>$null

$existingRemote = git remote | Where-Object { $_ -eq "origin" }
if ($existingRemote) {
    git remote set-url origin $GitRepoUrl
} else {
    git remote add origin $GitRepoUrl
}

git branch -M main
Write-Host "⬆️ در حال Push کردن پروژه به $GitRepoUrl ..." -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "🖥️ گام ۲: استقرار پروژه از Git روی سرور $ServerIp ..." -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green

$remoteCmd = @"
export GIT_REPO_URL='$GitRepoUrl'
export IG_ACCESS_TOKEN='$IgAccessToken'
export IG_USER_ID='$IgUserId'
export GEMINI_API_KEY='$GeminiApiKey'
if [ -d /opt/aria-ai-influencer/.git ]; then
  cd /opt/aria-ai-influencer && git pull origin main
else
  rm -rf /opt/aria-ai-influencer && git clone '$GitRepoUrl' /opt/aria-ai-influencer
fi
cd /opt/aria-ai-influencer
sed -i 's/$//' scripts/*.sh
chmod +x scripts/*.sh
./scripts/server_git_deploy.sh '$GitRepoUrl'
"@

ssh -t "$ServerUser@$ServerIp" $remoteCmd
