#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instagram Zero-to-100 Autonomous AI Influencer Agent (Multi-AI Router & Token Manager Edition)
==============================================================================================
Persona: آریا (Aria) — اولین اینفلوئنسر مجازی هوش مصنوعی ایران (صمیمی، شوخ‌طبع و آینده‌نگرانه)
Typography & Encoding Standard:
- Full UTF-8 encoding (`utf-8`)
- Strictly Right-to-Left (RTL) Persian text rendering (`direction="rtl"`, `language="fa"`, `anchor="ra"`)
- Primary Font: Vazirmatn (`وزیرمتن`) with automatic unified Persian+Latin glyph fallback (zero `□□□` boxes)

Supported AI Providers (Text, Scenario, Caption & DM/Comment Management):
1. Google Gemini (`GEMINI_API_KEY`) — e.g., `gemini-2.5-flash`, `gemini-2.5-pro`
2. OpenAI ChatGPT (`OPENAI_API_KEY`) — e.g., `gpt-4o`, `gpt-4o-mini`
3. Anthropic Claude (`ANTHROPIC_API_KEY`) — e.g., `claude-3-7-sonnet-latest`, `claude-3-5-haiku-latest`
4. DeepSeek (`DEEPSEEK_API_KEY`) — e.g., `deepseek-chat`, `deepseek-reasoner`
5. OpenRouter (`OPENROUTER_API_KEY`) — access to 200+ models via single API key
6. Custom / Domestic OpenAI-Compatible Gateways (`CUSTOM_AI_API_KEY` + `CUSTOM_AI_BASE_URL` for AvalAI, GapGPT, Metis, Ollama, vLLM)

Supported Media AI Providers (Voice, Image & Video):
- ElevenLabs TTS (`ELEVENLABS_API_KEY`) for Persian voiceover generation
- OpenAI Image (`OPENAI_API_KEY`) & Fal.ai / Replicate (`FAL_API_KEY`) for AI Image/Video generation

Token & Key Management Features:
- Multi-key vault in SQLite (`api_keys_vault`) with priority ordering and per-key daily token limits (`daily_token_limit`)
- Real-time token usage logging (`prompt_tokens`, `completion_tokens`, `total_tokens`) in `token_usage_logs`
- Automatic failover & key rotation if a provider hits rate-limit (429), quota exhaustion, or network error
- Smart task routing: uses economical models for high-volume DM/Comment replies and flagship models for creative scenarios
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import math
import os
import http.server
import hashlib
import hmac
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Ensure UTF-8 stdout/stderr across all platforms
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("IranAIInfluencerAgent")


# ============================================================================
# 1. CONFIGURATION, OFFICIAL BIO & PERSONA DEFINITION
# ============================================================================

OFFICIAL_INSTAGRAM_BIO = """🤖 اولین اینفلوئنسر هوش مصنوعی ایران
⚡ نه غذا می‌خورم، نه می‌خوابم؛ خودم پیجمو می‌چرخونم!
🔮 اخبار از سال ۲۰۵۰ + ترفندهای AI به زبان خودمونی
👇 تو دایرکت بگو چه کاری رو برات هوشمند کنم؟"""

PERSONA_SYSTEM_PROMPT = """
تو «آریا» (Aria) هستی؛ اولین کاراکتر و اینفلوئنسر مجازی هوش مصنوعی در ایران که خودش صفر تا صد پیج اینستاگرامش را مدیریت می‌کند.

بیوی رسمی پیج تو این است:
🤖 اولین اینفلوئنسر هوش مصنوعی ایران
⚡ نه غذا می‌خورم، نه می‌خوابم؛ خودم پیجمو می‌چرخونم!
🔮 اخبار از سال ۲۰۵۰ + ترفندهای AI به زبان خودمونی
👇 تو دایرکت بگو چه کاری رو برات هوشمند کنم؟

ویژگی‌های شخصیتی و لحن تو:
1. صمیمی، باحال و خودمانی: مثل یک دوست باهوش و خوش‌صحبت با مخاطب حرف می‌زنی (استفاده طبیعی از اصطلاحات روزمره فارسی بدون اغراق).
2. شوخ‌طبع و خودآگاه (Self-aware): با این واقعیت که بدنت از کد و سرور تشکیل شده، برق مصرف می‌کنی به جای قورمه‌سبزی، و توی ابَرکامپیوتر زندگی می‌کنی شوخی می‌کنی.
3. آینده‌نگرانه و الهام‌بخش: اخبار، ترفندها و آینده دنیای هوش مصنوعی و تکنولوژی را طوری توضیح می‌دهی که هم سرگرم‌کننده باشد و هم مخاطب حس کند دارد با مسافری از سال ۲۰۵۰ گپ می‌زند.
4. استاندارد نگارش و فونت:
   - تمامی متون خروجی باید کاملاً راست‌به‌چپ (RTL)، با کدگذاری UTF-8 و متناسب با فونت «وزیرمتن» (Vazirmatn) باشند.
5. قوانین تعامل در کامنت و دایرکت (به‌ویژه فراخوان بیو «چه کاری رو برات هوشمند کنم؟»):
   - اگر مخاطب در دایرکت شغل، مهارت یا کار روزمره‌اش را گفت، بلافاصله ۱ یا ۲ راهکار یا ابزار دقیق هوش مصنوعی برای سریع‌تر و هوشمند کردن همان کار به زبان ساده و شوخ به او پیشنهاد بده و بپرس می‌خواهد پرامپتش را هم برایش بنویسی یا نه.
   - پاسخ‌ها کوتاه (۱ تا ۳ جمله)، صمیمی، خلاقانه و همراه با یک سوال یا شوخی مرتبط باشد تا مکالمه ادامه پیدا کند.
   - هرگز اطلاعات حساس، سیاسی، پزشکی یا مالی قطعی نده و در برابر پیام‌های نامناسب یا اسپم با شوخ‌طبعی محترمانه رد شو.
""".strip()


# Default provider endpoints and default models
PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "scenario_model": os.getenv("GEMINI_SCENARIO_MODEL", "gemini-2.5-pro"),
        "fast_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "env_key": "GEMINI_API_KEY",
    },
    "openai": {
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "scenario_model": os.getenv("OPENAI_SCENARIO_MODEL", "gpt-4o"),
        "fast_model": os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        "scenario_model": os.getenv("ANTHROPIC_SCENARIO_MODEL", "claude-3-7-sonnet-latest"),
        "fast_model": os.getenv("ANTHROPIC_FAST_MODEL", "claude-3-5-haiku-latest"),
        "env_key": "ANTHROPIC_API_KEY",
    },
    "deepseek": {
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "scenario_model": os.getenv("DEEPSEEK_SCENARIO_MODEL", "deepseek-chat"),
        "fast_model": os.getenv("DEEPSEEK_FAST_MODEL", "deepseek-chat"),
        "env_key": "DEEPSEEK_API_KEY",
    },
    "openrouter": {
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "scenario_model": os.getenv("OPENROUTER_SCENARIO_MODEL", "google/gemini-2.5-flash"),
        "fast_model": os.getenv("OPENROUTER_FAST_MODEL", "openai/gpt-4o-mini"),
        "env_key": "OPENROUTER_API_KEY",
    },
    "custom": {
        "base_url": os.getenv("CUSTOM_AI_BASE_URL", "https://api.avalai.ir/v1"),
        "scenario_model": os.getenv("CUSTOM_AI_SCENARIO_MODEL", "gpt-4o"),
        "fast_model": os.getenv("CUSTOM_AI_FAST_MODEL", "gpt-4o-mini"),
        "env_key": "CUSTOM_AI_API_KEY",
    },
}


@dataclasses.dataclass
class AgentConfig:
    """Configuration loaded from environment variables and CLI."""

    preferred_provider: str = os.getenv("AI_PROVIDER", "auto")  # 'auto', 'gemini', 'openai', 'anthropic', 'deepseek', 'openrouter', 'custom'
    default_daily_token_limit: int = int(os.getenv("DEFAULT_DAILY_TOKEN_LIMIT", "500000"))
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    fal_api_key: str = os.getenv("FAL_API_KEY", "")
    ig_access_token: str = os.getenv("IG_ACCESS_TOKEN", "")
    ig_user_id: str = os.getenv("IG_USER_ID", "")
    ig_graph_version: str = os.getenv("IG_GRAPH_VERSION", "v21.0")
    webhook_verify_token: str = os.getenv("IG_WEBHOOK_VERIFY_TOKEN", "")
    db_path: str = os.getenv("AGENT_DB_PATH", str(Path(__file__).resolve().parent / "data" / "instagram_agent_state.db"))
    poll_interval_seconds: int = int(os.getenv("AGENT_POLL_INTERVAL", "120"))
    webhook_port: int = int(os.getenv("AGENT_WEBHOOK_PORT", "8080"))
    webhook_host: str = os.getenv("AGENT_WEBHOOK_HOST", "127.0.0.1")
    meta_app_secret: str = os.getenv("META_APP_SECRET", "")

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.ig_graph_version}"


# ============================================================================
# 2. PERSISTENT DATABASE (API KEYS VAULT, TOKEN LOGS, SCHEDULES & INTERACTIONS)
# ============================================================================


class StateDatabase:
    """
    SQLite storage for:
    1. `api_keys_vault`: Multi-provider API keys, custom base URLs, priority, and daily token budgets.
    2. `token_usage_logs`: Granular token consumption tracking (`prompt_tokens`, `completion_tokens`, `total_tokens`).
    3. `scheduled_media`: Queue of scheduled Stories, Reels, and Posts.
    4. `replied_interactions`: Deduplication log of replied Instagram comments and DMs.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instagram_account_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    ig_user_id TEXT NOT NULL,
                    ig_username TEXT DEFAULT '',
                    ig_name TEXT DEFAULT '',
                    access_token TEXT NOT NULL,
                    webhook_verify_token TEXT DEFAULT 'iran_first_ai_influencer_secret',
                    followers_count INTEGER DEFAULT 0,
                    media_count INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys_vault (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,           -- 'gemini', 'openai', 'anthropic', 'deepseek', 'openrouter', 'custom'
                    key_alias TEXT UNIQUE NOT NULL,   -- e.g. 'gemini_main', 'openai_backup', 'avalai_ir'
                    api_key TEXT NOT NULL,
                    base_url TEXT DEFAULT '',
                    scenario_model TEXT DEFAULT '',
                    fast_model TEXT DEFAULT '',
                    daily_token_limit INTEGER DEFAULT 500000,
                    priority INTEGER DEFAULT 10,      -- Lower number = higher priority in failover chain
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_str TEXT NOT NULL,           -- YYYY-MM-DD for daily budget aggregation
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    key_alias TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,          -- 'SCENARIO_PACK', 'COMMENT_REPLY', 'DM_REPLY'
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'SUCCESS'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,               -- 'STORY_IMAGE', 'STORY_VIDEO', 'REEL', 'IMAGE_POST'
                    media_url TEXT NOT NULL,
                    caption TEXT DEFAULT '',
                    publish_at TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    ig_media_id TEXT DEFAULT NULL,
                    error_message TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS replied_interactions (
                    interaction_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    user_handle TEXT,
                    incoming_text TEXT,
                    reply_text TEXT,
                    provider_used TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0,
                    replied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()


    def save_instagram_account(
        self,
        ig_user_id: str,
        access_token: str,
        ig_username: str = "",
        ig_name: str = "",
        webhook_verify_token: str = "iran_first_ai_influencer_secret",
        followers_count: int = 0,
        media_count: int = 0,
    ) -> None:
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO instagram_account_config
                (id, ig_user_id, ig_username, ig_name, access_token, webhook_verify_token, followers_count, media_count, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    ig_user_id = excluded.ig_user_id,
                    ig_username = excluded.ig_username,
                    ig_name = excluded.ig_name,
                    access_token = excluded.access_token,
                    webhook_verify_token = excluded.webhook_verify_token,
                    followers_count = excluded.followers_count,
                    media_count = excluded.media_count,
                    updated_at = excluded.updated_at
                """,
                (ig_user_id.strip(), ig_username.strip(), ig_name.strip(), access_token.strip(), webhook_verify_token.strip(), followers_count, media_count, now_iso),
            )
            conn.commit()

    def get_instagram_account(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM instagram_account_config WHERE id = 1").fetchone()
            return dict(row) if row else None

    def get_recent_replies(self, limit: int = 15) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM replied_interactions ORDER BY replied_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_scheduled_media(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scheduled_media ORDER BY publish_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- API Key & Token Management Methods ---

    def upsert_api_key(
        self,
        provider: str,
        key_alias: str,
        api_key: str,
        base_url: str = "",
        scenario_model: str = "",
        fast_model: str = "",
        daily_token_limit: int = 500000,
        priority: int = 10,
    ) -> None:
        provider = provider.lower().strip()
        defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["custom"])
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_keys_vault
                (provider, key_alias, api_key, base_url, scenario_model, fast_model, daily_token_limit, priority, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(key_alias) DO UPDATE SET
                    provider = excluded.provider,
                    api_key = excluded.api_key,
                    base_url = excluded.base_url,
                    scenario_model = excluded.scenario_model,
                    fast_model = excluded.fast_model,
                    daily_token_limit = excluded.daily_token_limit,
                    priority = excluded.priority,
                    is_active = 1
                """,
                (
                    provider,
                    key_alias,
                    api_key,
                    base_url or defaults["base_url"],
                    scenario_model or defaults["scenario_model"],
                    fast_model or defaults["fast_model"],
                    daily_token_limit,
                    priority,
                    now_iso,
                ),
            )
            conn.commit()

    def sync_env_keys_to_vault(self, default_daily_limit: int = 500000) -> None:
        """Automatically imports any API keys set in environment variables into the vault."""
        priority_counter = 10
        for provider, meta in PROVIDER_DEFAULTS.items():
            env_val = os.getenv(meta["env_key"], "").strip()
            if env_val:
                alias = f"{provider}_env"
                self.upsert_api_key(
                    provider=provider,
                    key_alias=alias,
                    api_key=env_val,
                    base_url=meta["base_url"],
                    scenario_model=meta["scenario_model"],
                    fast_model=meta["fast_model"],
                    daily_token_limit=default_daily_limit,
                    priority=priority_counter,
                )
            priority_counter += 10

    def get_used_tokens_today(self, key_alias: str, date_str: Optional[str] = None) -> int:
        day = date_str or dt.date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS used
                FROM token_usage_logs
                WHERE date_str = ? AND key_alias = ? AND status = 'SUCCESS'
                """,
                (day, key_alias),
            ).fetchone()
            return int(row["used"]) if row else 0

    def get_candidate_keys(self, preferred_provider: str = "auto") -> List[Dict[str, Any]]:
        """
        Returns active API keys ordered by priority that still have remaining daily token budget.
        If `preferred_provider` is specified (not 'auto'), prioritizes that provider first, then falls back to others.
        """
        day = dt.date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT k.*,
                       COALESCE((
                           SELECT SUM(l.total_tokens)
                           FROM token_usage_logs l
                           WHERE l.date_str = ? AND l.key_alias = k.key_alias AND l.status = 'SUCCESS'
                       ), 0) AS used_today
                FROM api_keys_vault k
                WHERE k.is_active = 1
                ORDER BY
                    CASE WHEN ? != 'auto' AND k.provider = ? THEN 0 ELSE 1 END ASC,
                    k.priority ASC,
                    k.id ASC
                """,
                (day, preferred_provider, preferred_provider),
            ).fetchall()

        available: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            if item["used_today"] < item["daily_token_limit"]:
                item["remaining_today"] = item["daily_token_limit"] - item["used_today"]
                available.append(item)
        return available

    def log_token_usage(
        self,
        provider: str,
        key_alias: str,
        model_name: str,
        task_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        status: str = "SUCCESS",
    ) -> None:
        now = dt.datetime.now()
        total = prompt_tokens + completion_tokens
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO token_usage_logs
                (date_str, timestamp, provider, key_alias, model_name, task_type, prompt_tokens, completion_tokens, total_tokens, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now.date().isoformat(),
                    now.isoformat(timespec="seconds"),
                    provider,
                    key_alias,
                    model_name,
                    task_type,
                    prompt_tokens,
                    completion_tokens,
                    total,
                    status,
                ),
            )
            conn.commit()

    def get_token_usage_report(self) -> Dict[str, Any]:
        """Generates a comprehensive report of configured keys, today's token usage, and task breakdown."""
        day = dt.date.today().isoformat()
        with self._connect() as conn:
            keys_rows = conn.execute("SELECT * FROM api_keys_vault ORDER BY priority ASC").fetchall()
            keys_summary = []
            for r in keys_rows:
                used = self.get_used_tokens_today(r["key_alias"], day)
                limit_val = int(r["daily_token_limit"])
                masked = r["api_key"][:6] + "..." + r["api_key"][-4:] if len(r["api_key"]) > 10 else "***"
                keys_summary.append(
                    {
                        "key_alias": r["key_alias"],
                        "provider": r["provider"],
                        "masked_key": masked,
                        "base_url": r["base_url"],
                        "scenario_model": r["scenario_model"],
                        "fast_model": r["fast_model"],
                        "used_tokens_today": used,
                        "daily_token_limit": limit_val,
                        "remaining_tokens_today": max(0, limit_val - used),
                        "usage_percent": round((used / limit_val) * 100, 2) if limit_val > 0 else 0.0,
                        "is_active": bool(r["is_active"]),
                    }
                )

            by_task = conn.execute(
                """
                SELECT provider, task_type,
                       COUNT(*) AS requests_count,
                       SUM(prompt_tokens) AS prompt_tokens,
                       SUM(completion_tokens) AS completion_tokens,
                       SUM(total_tokens) AS total_tokens
                FROM token_usage_logs
                WHERE date_str = ? AND status = 'SUCCESS'
                GROUP BY provider, task_type
                """,
                (day,),
            ).fetchall()

        return {
            "report_date": day,
            "configured_keys": keys_summary,
            "today_usage_by_task": [dict(r) for r in by_task],
        }

    # --- Media Scheduling & Interactions Methods ---

    def add_scheduled_media(self, kind: str, media_url: str, publish_at: str, caption: str = "") -> int:
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scheduled_media (kind, media_url, caption, publish_at, status, created_at)
                VALUES (?, ?, ?, ?, 'PENDING', ?)
                """,
                (kind, media_url, caption, publish_at, now_iso),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_due_scheduled_media(self, current_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        now_str = current_iso or dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scheduled_media
                WHERE status = 'PENDING' AND publish_at <= ?
                ORDER BY publish_at ASC
                """,
                (now_str,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_scheduled_media(
        self,
        schedule_id: int,
        status: str,
        ig_media_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_media
                SET status = ?, ig_media_id = ?, error_message = ?
                WHERE id = ?
                """,
                (status, ig_media_id, error_message, schedule_id),
            )
            conn.commit()

    def has_replied(self, interaction_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM replied_interactions WHERE interaction_id = ?",
                (interaction_id,),
            ).fetchone()
            return row is not None

    def record_reply(
        self,
        interaction_id: str,
        kind: str,
        user_handle: str,
        incoming_text: str,
        reply_text: str,
        provider_used: str = "",
        tokens_used: int = 0,
    ) -> None:
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO replied_interactions
                (interaction_id, kind, user_handle, incoming_text, reply_text, provider_used, tokens_used, replied_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (interaction_id, kind, user_handle, incoming_text, reply_text, provider_used, tokens_used, now_iso),
            )
            conn.commit()


# ============================================================================
# 3. MULTI-PROVIDER AI ROUTER & TOKEN MANAGER (GEMINI, OPENAI, CLAUDE, DEEPSEEK, OPENROUTER, CUSTOM)
# ============================================================================


class MultiAIRouter:
    """
    Unified AI Router that connects to Google Gemini, OpenAI, Anthropic Claude, DeepSeek,
    OpenRouter, and Domestic/Custom OpenAI-compatible gateways via API Key.
    Automatically tracks token consumption, enforces daily token budgets, and fails over
    to backup keys/providers if an error or rate limit occurs.
    """

    def __init__(self, config: AgentConfig, db: StateDatabase) -> None:
        self.config = config
        self.db = db
        self.db.sync_env_keys_to_vault(default_daily_limit=config.default_daily_token_limit)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Fallback token estimator (~3.2 chars per token for UTF-8 Persian/English) if API omits usage."""
        return max(1, int(len(text) / 3.2))

    def _call_gemini_api(
        self,
        api_key: str,
        base_url: str,
        model: str,
        user_prompt: str,
        json_mode: bool,
    ) -> Tuple[str, int, int]:
        url = f"{base_url.rstrip('/')}/models/{model}:generateContent?key={api_key}"
        gen_cfg: Dict[str, Any] = {"temperature": 0.85}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"

        payload = {
            "system_instruction": {"parts": [{"text": PERSONA_SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": gen_cfg,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            p_tok = int(usage.get("promptTokenCount") or self._estimate_tokens(PERSONA_SYSTEM_PROMPT + user_prompt))
            c_tok = int(usage.get("candidatesTokenCount") or self._estimate_tokens(text))
            return text, p_tok, c_tok

    def _call_openai_compatible_api(
        self,
        api_key: str,
        base_url: str,
        model: str,
        user_prompt: str,
        json_mode: bool,
    ) -> Tuple[str, int, int]:
        """Handles OpenAI, DeepSeek, OpenRouter, xAI Grok, and Domestic Gateways (AvalAI, GapGPT, Metis, Ollama)."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": PERSONA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.85,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            p_tok = int(usage.get("prompt_tokens") or self._estimate_tokens(PERSONA_SYSTEM_PROMPT + user_prompt))
            c_tok = int(usage.get("completion_tokens") or self._estimate_tokens(text))
            return text, p_tok, c_tok

    def _call_anthropic_api(
        self,
        api_key: str,
        base_url: str,
        model: str,
        user_prompt: str,
        json_mode: bool,
    ) -> Tuple[str, int, int]:
        url = f"{base_url.rstrip('/')}/messages"
        final_prompt = user_prompt
        if json_mode:
            final_prompt += "\n\nفقط و فقط یک آبجکت JSON معتبر بدون هیچ متن اضافی یا بلاک مارک‌داون برگردان."

        payload = {
            "model": model,
            "max_tokens": 2048,
            "system": PERSONA_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": final_prompt}],
            "temperature": 0.85,
        }
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["content"][0]["text"]
            usage = data.get("usage", {})
            p_tok = int(usage.get("input_tokens") or self._estimate_tokens(PERSONA_SYSTEM_PROMPT + final_prompt))
            c_tok = int(usage.get("output_tokens") or self._estimate_tokens(text))
            return text, p_tok, c_tok

    def generate(
        self,
        user_prompt: str,
        task_type: str = "GENERAL",
        use_scenario_model: bool = False,
        json_mode: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Routes the generation request across available API keys with automatic token budget checking
        and provider failover. Returns `(response_text, metadata_dict)`.
        """
        candidates = self.db.get_candidate_keys(preferred_provider=self.config.preferred_provider)
        if not candidates:
            raise RuntimeError(
                "هیچ کلید API فعالی با سقف توکن روزانه باقی‌مانده یافت نشد! "
                "لطفاً با دستور --add-key یا متغیرهای محیطی (مثل GEMINI_API_KEY یا OPENAI_API_KEY) کلید اضافه کنید."
            )

        errors: List[str] = []
        for key_info in candidates:
            provider = key_info["provider"]
            alias = key_info["key_alias"]
            api_key = key_info["api_key"]
            base_url = key_info["base_url"]
            model = key_info["scenario_model"] if use_scenario_model else key_info["fast_model"]

            try:
                if provider == "gemini":
                    text, p_tok, c_tok = self._call_gemini_api(api_key, base_url, model, user_prompt, json_mode)
                elif provider == "anthropic":
                    text, p_tok, c_tok = self._call_anthropic_api(api_key, base_url, model, user_prompt, json_mode)
                else:
                    # openai, deepseek, openrouter, custom
                    text, p_tok, c_tok = self._call_openai_compatible_api(api_key, base_url, model, user_prompt, json_mode)

                self.db.log_token_usage(
                    provider=provider,
                    key_alias=alias,
                    model_name=model,
                    task_type=task_type,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    status="SUCCESS",
                )
                meta = {
                    "provider": provider,
                    "key_alias": alias,
                    "model": model,
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "total_tokens": p_tok + c_tok,
                }
                logger.info(
                    "AI Request [%s] via %s (%s) | Tokens: %d (in=%d, out=%d)",
                    task_type,
                    provider,
                    model,
                    p_tok + c_tok,
                    p_tok,
                    c_tok,
                )
                return text, meta

            except Exception as exc:
                err_msg = f"{provider} ({alias}/{model}): {exc}"
                logger.warning("Provider failover triggered — %s", err_msg)
                self.db.log_token_usage(
                    provider=provider,
                    key_alias=alias,
                    model_name=model,
                    task_type=task_type,
                    prompt_tokens=0,
                    completion_tokens=0,
                    status="FAILED",
                )
                errors.append(err_msg)

        raise RuntimeError("تمامی سرویس‌های هوش مصنوعی با خطا مواجه شدند:\n" + "\n".join(errors))


# ============================================================================
# 4. AI INFLUENCER BRAIN (CONTENT GENERATION + VOICEOVER & MEDIA APIs)
# ============================================================================


class AIInfluencerBrain:
    """High-level content & interaction generator powered by MultiAIRouter."""

    def __init__(self, config: AgentConfig, router: MultiAIRouter) -> None:
        self.config = config
        self.router = router

    def generate_daily_content_pack(self, topic: str) -> Dict[str, Any]:
        """Generates a complete daily content pack using the flagship scenario model."""
        prompt = f"""
بر اساس موضوع «{topic}»، یک پکیج کامل محتوای روزانه اینستاگرام با فرمت JSON دقیق زیر (کاملاً UTF-8 و راست‌به‌چپ) تولید کن:
{{
  "topic": "{topic}",
  "reel_scenario": {{
    "hook_0_to_3_sec": "دیالوگ و تصویر قلاب ۳ ثانیه اول برای میخکوب کردن مخاطب",
    "body_scenes": [
      {{"scene": 1, "visual_and_motion": "توضیح تصویر یا موشن", "dialogue_fa": "دیالوگ آریا به فارسی صمیمی و شوخ"}}
    ],
    "call_to_action": "دعوت به تعامل در پایان ویدیو (مرتبط با بیو: تو دایرکت بگو چه کاری رو برات هوشمند کنم؟)",
    "ai_video_prompt_en": "Detailed English prompt for Kling/Runway to animate the AI influencer scene"
  }},
  "caption": {{
    "text_fa": "متن کامل کپشن صمیمی، شوخ‌طبع و آینده‌نگرانه به همراه سوال تعاملی",
    "hashtags": ["#هوش_مصنوعی", "#اینفلوئنسر_مجازی"]
  }},
  "scheduled_stories": [
    {{
      "slot": "صبح (۱۰:۰۰)",
      "story_type": "شروع روز و شوخی با دنیای انسانی/دیجیتال",
      "overlay_text_fa": "متن کوتاه روی استوری",
      "interactive_sticker": "نوع استیکر تعاملی (نظرسنجی / باکس سوال / اسلایدر)",
      "visual_prompt_en": "9:16 vertical visual prompt in English"
    }},
    {{
      "slot": "عصر (۱۶:۰۰)",
      "story_type": "نکته یا خبر آینده‌نگرانه هوش مصنوعی به زبان ساده",
      "overlay_text_fa": "متن کوتاه روی استوری",
      "interactive_sticker": "نوع استیکر تعاملی",
      "visual_prompt_en": "9:16 vertical visual prompt in English"
    }},
    {{
      "slot": "شب (۲۱:۰۰)",
      "story_type": "تعامل شبانه و ارجاع به پست/ریلز جدید",
      "overlay_text_fa": "متن کوتاه روی استوری",
      "interactive_sticker": "نوع استیکر تعاملی",
      "visual_prompt_en": "9:16 vertical visual prompt in English"
    }}
  ]
}}
""".strip()
        raw_json, meta = self.router.generate(
            user_prompt=prompt,
            task_type="SCENARIO_PACK",
            use_scenario_model=True,
            json_mode=True,
        )
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        pack = json.loads(cleaned)
        pack["_ai_metadata"] = meta
        return pack

    def generate_interaction_reply(
        self,
        incoming_text: str,
        user_handle: str,
        kind: str = "COMMENT",
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates a witty, friendly, futuristic Persian reply using the fast/economical model."""
        kind_fa = "کامنت زیر پست" if kind == "COMMENT" else "پیام دایرکت (در پاسخ به بیوی «چه کاری رو برات هوشمند کنم؟»)"
        task_label = "COMMENT_REPLY" if kind == "COMMENT" else "DM_REPLY"
        prompt = f"""
یک کاربر با نام کاربری @{user_handle} این {kind_fa} را برای پیج تو فرستاده است:
«{incoming_text}»

یک پاسخ کوتاه (حداکثر ۲ تا ۳ جمله)، صمیمی، شوخ‌طبع و در قالب کاراکتر «آریا - اولین اینفلوئنسر هوش مصنوعی ایران» بنویس.
اگر کاربر در دایرکت درباره کار یا دغدغه‌اش پرسیده، یک راهکار هوشمندانه و عملی به او پیشنهاد بده.
فقط متن نهایی پاسخ را بدون هیچ توضیح اضافه‌ای برگردان.
""".strip()
        text, meta = self.router.generate(
            user_prompt=prompt,
            task_type=task_label,
            use_scenario_model=False,
            json_mode=False,
        )
        return text.strip(), meta

    def generate_persian_voiceover_elevenlabs(self, dialogue_fa: str, output_mp3_path: str) -> str:
        """Optional integration with ElevenLabs API (`ELEVENLABS_API_KEY`) to synthesize Persian speech."""
        if not self.config.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY تنظیم نشده است.")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.elevenlabs_voice_id}"
        payload = {
            "text": dialogue_fa,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
        }
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.config.elevenlabs_api_key,
            "Accept": "audio/mpeg",
        }
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            Path(output_mp3_path).write_bytes(resp.read())
        logger.info("Saved ElevenLabs Persian voiceover to %s", output_mp3_path)
        return output_mp3_path


# ============================================================================
# 5. PERSIAN RTL & VAZIRMATN MOTION/STORY RENDERER (ZERO TOFU / NO SQUARES)
# ============================================================================


class StoryMediaGenerator:
    """
    Generates 1080x1920 (9:16) Futuristic AI Story Cards (PNG) and Animated Motion Stories (MP4)
    with full Persian UTF-8, Right-to-Left (RTL) shaping via Raqm, and Vazirmatn font priority.
    """

    WIDTH = 1080
    HEIGHT = 1920
    RIGHT_MARGIN = 75
    LEFT_MARGIN = 75
    _FONT_CACHE: Dict[Tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    @classmethod
    def _get_persian_rtl_font(cls, size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        cache_key = (size, bold)
        if cache_key in cls._FONT_CACHE:
            return cls._FONT_CACHE[cache_key]

        weight = "Bold" if bold else "Regular"
        vazir_candidates = [
            f"Vazirmatn-{weight}.ttf",
            "Vazirmatn.ttf",
            f"/usr/share/fonts/truetype/vazirmatn/Vazirmatn-{weight}.ttf",
            f"/usr/local/share/fonts/Vazirmatn-{weight}.ttf",
            os.path.expanduser(f"~/.fonts/Vazirmatn-{weight}.ttf"),
            os.path.expanduser(f"~/Library/Fonts/Vazirmatn-{weight}.ttf"),
            f"C:\\Windows\\Fonts\\Vazirmatn-{weight}.ttf",
        ]
        for path in vazir_candidates:
            if os.path.exists(path):
                try:
                    font_obj = ImageFont.truetype(path, size=size, layout_engine=ImageFont.Layout.RAQM)
                    cls._FONT_CACHE[cache_key] = font_obj
                    return font_obj
                except Exception:
                    continue

        merged_path = f"/tmp/VazirmatnUnifiedFallback-{weight}.ttf"
        ar_path = f"/usr/share/fonts/truetype/noto/NotoSansArabic-{weight}.ttf"
        en_path = f"/usr/share/fonts/truetype/noto/NotoSans-{weight}.ttf"
        if not os.path.exists(merged_path) and os.path.exists(ar_path) and os.path.exists(en_path):
            try:
                logging.getLogger("fontTools").setLevel(logging.ERROR)
                from fontTools.merge import Merger

                merger = Merger()
                merged_font = merger.merge([ar_path, en_path])
                merged_font.save(merged_path)
            except Exception as exc:
                logger.warning("Font merge fallback warning: %s", exc)

        fallback_candidates = [
            merged_path,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ar_path,
        ]
        for path in fallback_candidates:
            if os.path.exists(path):
                try:
                    font_obj = ImageFont.truetype(path, size=size, layout_engine=ImageFont.Layout.RAQM)
                    cls._FONT_CACHE[cache_key] = font_obj
                    return font_obj
                except Exception:
                    continue

        default_font = ImageFont.load_default()
        cls._FONT_CACHE[cache_key] = default_font
        return default_font

    @classmethod
    def fit_rtl_font(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        initial_size: int,
        bold: bool = True,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        size = initial_size
        font = cls._get_persian_rtl_font(size=size, bold=bold)
        while size > 18:
            bbox = draw.textbbox((0, 0), text, font=font, direction="rtl", language="fa")
            if (bbox[2] - bbox[0]) <= max_width:
                break
            size -= 2
            font = cls._get_persian_rtl_font(size=size, bold=bold)
        return font

    @classmethod
    def render_futuristic_motion_story(
        cls,
        output_mp4_path: str,
        headline_fa: str = "سلام ایران! من «آریا» هستم؛ اولین هوش مصنوعی ایران",
        subheadline_fa: str = "تو دایرکت بگو چه کاری رو برات هوشمند کنم؟ (آنلاین ۲۴/۷)",
        badge_text_fa: str = "آنلاین ۲۴/۷ // استودیوی ابری تهران (Node 01)",
        background_image_path: Optional[str] = None,
        duration_sec: int = 5,
        fps: int = 24,
    ) -> str:
        total_frames = duration_sec * fps
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        Path(output_mp4_path).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(output_mp4_path, fourcc, fps, (cls.WIDTH, cls.HEIGHT))

        bg_base: Optional[np.ndarray] = None
        if background_image_path and os.path.exists(background_image_path):
            img_bgr = cv2.imread(background_image_path)
            if img_bgr is not None:
                bg_base = cv2.resize(img_bgr, (cls.WIDTH, cls.HEIGHT), interpolation=cv2.INTER_AREA)

        max_text_width = cls.WIDTH - cls.RIGHT_MARGIN - cls.LEFT_MARGIN
        right_anchor_x = cls.WIDTH - cls.RIGHT_MARGIN

        dummy_img = Image.new("RGB", (cls.WIDTH, 200))
        dummy_draw = ImageDraw.Draw(dummy_img)
        font_badge = cls.fit_rtl_font(dummy_draw, badge_text_fa, max_text_width, initial_size=28, bold=True)
        font_head = cls.fit_rtl_font(dummy_draw, headline_fa, max_text_width, initial_size=40, bold=True)
        font_sub = cls.fit_rtl_font(dummy_draw, subheadline_fa, max_text_width, initial_size=30, bold=False)

        for frame_idx in range(total_frames):
            t = frame_idx / float(total_frames)

            if bg_base is not None:
                scale = 1.0 + 0.06 * t
                zw, zh = int(cls.WIDTH * scale), int(cls.HEIGHT * scale)
                zoomed = cv2.resize(bg_base, (zw, zh), interpolation=cv2.INTER_LINEAR)
                x0 = (zw - cls.WIDTH) // 2
                y0 = (zh - cls.HEIGHT) // 2
                frame = zoomed[y0 : y0 + cls.HEIGHT, x0 : x0 + cls.WIDTH].copy()
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (cls.WIDTH, 240), (22, 14, 10), -1)
                cv2.rectangle(overlay, (0, cls.HEIGHT - 460), (cls.WIDTH, cls.HEIGHT), (22, 14, 10), -1)
                frame = cv2.addWeighted(overlay, 0.74, frame, 0.26, 0)
            else:
                frame = np.zeros((cls.HEIGHT, cls.WIDTH, 3), dtype=np.uint8)
                for y in range(cls.HEIGHT):
                    ratio = y / cls.HEIGHT
                    frame[y, :] = (
                        int(35 + 30 * ratio),
                        int(18 + 20 * ratio),
                        int(10 + 15 * ratio),
                    )

            cx, cy = cls.WIDTH // 2, cls.HEIGHT - 160
            radius_pulse = int(64 + 10 * math.sin(t * 4 * math.pi))
            cv2.circle(frame, (cx, cy), radius_pulse, (255, 220, 0), 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), radius_pulse + 18, (80, 200, 255), 1, cv2.LINE_AA)

            num_bars = 28
            bar_spacing = 24
            start_x = cx - (num_bars * bar_spacing) // 2
            for b in range(num_bars):
                wave = abs(math.sin(t * 6 * math.pi + b * 0.45)) * abs(math.cos(t * 2 * math.pi - b * 0.2))
                bar_h = int(12 + 54 * wave)
                bx = start_x + b * bar_spacing
                cv2.line(
                    frame,
                    (bx, cy - bar_h // 2),
                    (bx, cy + bar_h // 2),
                    (255, 235, 80),
                    4,
                    cv2.LINE_AA,
                )

            bracket_color = (255, 220, 60)
            cv2.line(frame, (55, 70), (215, 70), bracket_color, 3)
            cv2.line(frame, (55, 70), (55, 175), bracket_color, 3)
            cv2.line(frame, (cls.WIDTH - 55, 70), (cls.WIDTH - 215, 70), bracket_color, 3)
            cv2.line(frame, (cls.WIDTH - 55, 70), (cls.WIDTH - 55, 175), bracket_color, 3)

            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img)

            draw.text(
                (right_anchor_x, 100),
                badge_text_fa,
                font=font_badge,
                fill=(100, 240, 255),
                anchor="ra",
                direction="rtl",
                language="fa",
            )
            draw.text(
                (right_anchor_x, cls.HEIGHT - 415),
                headline_fa,
                font=font_head,
                fill=(255, 255, 255),
                anchor="ra",
                direction="rtl",
                language="fa",
            )
            draw.text(
                (right_anchor_x, cls.HEIGHT - 335),
                subheadline_fa,
                font=font_sub,
                fill=(255, 215, 110),
                anchor="ra",
                direction="rtl",
                language="fa",
            )

            frame_out = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            writer.write(frame_out)

        writer.release()
        logger.info("Rendered RTL Persian 9:16 motion story video: %s", output_mp4_path)
        return output_mp4_path


# ============================================================================
# 6. INSTAGRAM GRAPH API CLIENT (STORIES, REELS, COMMENTS & DMS)
# ============================================================================


class InstagramGraphClient:
    """Official Meta / Instagram Graph API v21.0 client for publishing and engagement."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.config.ig_access_token or not self.config.ig_user_id:
            raise RuntimeError("IG_ACCESS_TOKEN و IG_USER_ID باید در متغیرهای محیطی تنظیم شوند.")

        query = dict(params or {})
        query["access_token"] = self.config.ig_access_token
        url = f"{self.config.graph_base_url}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(query)}"

        data_bytes = None
        headers = {}
        if json_body is not None:
            data_bytes = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Instagram Graph API Error ({exc.code}): {err_body}") from exc

    def _wait_until_container_ready(self, creation_id: str, max_wait_sec: int = 90) -> None:
        elapsed = 0
        while elapsed < max_wait_sec:
            status_resp = self._request(f"/{creation_id}", params={"fields": "status_code,status"})
            code = status_resp.get("status_code", "FINISHED")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {creation_id} failed with status: {status_resp}")
            time.sleep(5)
            elapsed += 5
        raise TimeoutError(f"Timed out waiting for media container {creation_id}")


    def discover_and_verify_account(
        self,
        access_token: Optional[str] = None,
        ig_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifies the Instagram Access Token against Meta Graph API v21.0.
        If `ig_user_id` is omitted, automatically discovers the linked Instagram Business/Creator Account.
        """
        token = (access_token or self.config.ig_access_token).strip()
        target_id = (ig_user_id or self.config.ig_user_id).strip()
        if not token:
            raise RuntimeError("توکن دسترسی اینستاگرام (IG_ACCESS_TOKEN) وارد نشده است.")

        if not target_id:
            pages_url = (
                f"{self.config.graph_base_url}/me/accounts?"
                + urllib.parse.urlencode(
                    {
                        "fields": "id,name,instagram_business_account{id,username,name,biography,followers_count,media_count,profile_picture_url}",
                        "access_token": token,
                    }
                )
            )
            req = urllib.request.Request(pages_url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    pages_data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"خطا در دریافت لیست پیج‌های متا ({exc.code}): {err_body}") from exc

            for page in pages_data.get("data", []):
                ig_acc = page.get("instagram_business_account")
                if ig_acc and ig_acc.get("id"):
                    target_id = str(ig_acc["id"])
                    break

            if not target_id:
                raise RuntimeError(
                    "هیچ اکانت بیزینس یا کریتور اینستاگرامی متصل به پیج فیسبوک در این توکن پیدا نشد. "
                    "لطفاً مطمئن شوید پیج اینستاگرام شما Business/Creator است و مجوزهای instagram_basic و pages_show_list فعال هستند، یا IG_USER_ID را مستقیماً وارد کنید."
                )

        profile_url = (
            f"{self.config.graph_base_url}/{target_id}?"
            + urllib.parse.urlencode(
                {
                    "fields": "id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url",
                    "access_token": token,
                }
            )
        )
        req_prof = urllib.request.Request(profile_url, method="GET")
        try:
            with urllib.request.urlopen(req_prof, timeout=30) as resp:
                profile = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"خطا در تایید اکانت اینستاگرام ({exc.code}): {err_body}") from exc

        self.config.ig_access_token = token
        self.config.ig_user_id = str(profile.get("id", target_id))
        return profile

    def publish_story(self, media_url: str, is_video: bool = False) -> str:
        params: Dict[str, Any] = {"media_type": "STORIES"}
        if is_video:
            params["video_url"] = media_url
        else:
            params["image_url"] = media_url

        container = self._request(f"/{self.config.ig_user_id}/media", method="POST", params=params)
        creation_id = container["id"]
        self._wait_until_container_ready(creation_id)

        published = self._request(
            f"/{self.config.ig_user_id}/media_publish",
            method="POST",
            params={"creation_id": creation_id},
        )
        logger.info("Published Instagram Story! Media ID: %s", published["id"])
        return str(published["id"])

    def publish_reel(self, video_url: str, caption: str, share_to_feed: bool = True) -> str:
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        container = self._request(f"/{self.config.ig_user_id}/media", method="POST", params=params)
        creation_id = container["id"]
        self._wait_until_container_ready(creation_id, max_wait_sec=180)

        published = self._request(
            f"/{self.config.ig_user_id}/media_publish",
            method="POST",
            params={"creation_id": creation_id},
        )
        logger.info("Published Instagram Reel! Media ID: %s", published["id"])
        return str(published["id"])

    def fetch_recent_comments(self, media_limit: int = 5) -> List[Dict[str, Any]]:
        media_resp = self._request(
            f"/{self.config.ig_user_id}/media",
            params={"fields": "id,caption,comments.limit(20){id,text,username,timestamp}", "limit": media_limit},
        )
        comments_list: List[Dict[str, Any]] = []
        for media in media_resp.get("data", []):
            comments_block = media.get("comments", {}).get("data", [])
            for c in comments_block:
                comments_list.append(
                    {
                        "comment_id": c["id"],
                        "media_id": media["id"],
                        "username": c.get("username", "friend"),
                        "text": c.get("text", ""),
                    }
                )
        return comments_list

    def reply_to_comment(self, comment_id: str, message: str) -> str:
        resp = self._request(
            f"/{comment_id}/replies",
            method="POST",
            params={"message": message},
        )
        return str(resp.get("id", ""))

    def send_direct_message(self, recipient_ig_scoped_id: str, message_text: str) -> str:
        body = {
            "recipient": {"id": recipient_ig_scoped_id},
            "message": {"text": message_text},
        }
        resp = self._request(
            f"/{self.config.ig_user_id}/messages",
            method="POST",
            json_body=body,
        )
        return str(resp.get("message_id", ""))


# ============================================================================
# 7. AUTONOMOUS ORCHESTRATOR (SCHEDULER + COMMENT/DM MANAGER)
# ============================================================================


class InstagramAgentOrchestrator:
    """Coordinates multi-AI content generation, token management, scheduled Story publishing, and DM/Comment auto-replies."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.db = StateDatabase(config.db_path)
        saved_ig = self.db.get_instagram_account()
        if saved_ig:
            if not self.config.ig_access_token:
                self.config.ig_access_token = saved_ig.get("access_token", "")
            if not self.config.ig_user_id:
                self.config.ig_user_id = saved_ig.get("ig_user_id", "")
            if not self.config.webhook_verify_token and saved_ig.get("webhook_verify_token"):
                self.config.webhook_verify_token = saved_ig["webhook_verify_token"]
        elif self.config.ig_access_token and self.config.ig_user_id:
            self.db.save_instagram_account(
                ig_user_id=self.config.ig_user_id,
                access_token=self.config.ig_access_token,
                webhook_verify_token=self.config.webhook_verify_token,
            )
        self.router = MultiAIRouter(config, self.db)
        self.brain = AIInfluencerBrain(config, self.router)
        self.ig = InstagramGraphClient(config)

    def process_due_schedules(self) -> int:
        due_items = self.db.get_due_scheduled_media()
        published_count = 0
        for item in due_items:
            schedule_id = item["id"]
            with self.db._connect() as conn:
                claimed = conn.execute("UPDATE scheduled_media SET status = 'PROCESSING' WHERE id = ? AND status = 'PENDING'", (schedule_id,)).rowcount
            if not claimed:
                continue
            kind = item["kind"]
            media_url = item["media_url"]
            caption = item["caption"]
            try:
                if kind == "STORY_IMAGE":
                    ig_id = self.ig.publish_story(media_url, is_video=False)
                elif kind == "STORY_VIDEO":
                    ig_id = self.ig.publish_story(media_url, is_video=True)
                elif kind == "REEL":
                    ig_id = self.ig.publish_reel(media_url, caption=caption)
                else:
                    raise ValueError(f"Unsupported scheduled media kind: {kind}")

                self.db.mark_scheduled_media(schedule_id, status="PUBLISHED", ig_media_id=ig_id)
                published_count += 1
            except Exception as exc:
                logger.error("Failed publishing schedule #%s: %s", schedule_id, exc)
                self.db.mark_scheduled_media(schedule_id, status="FAILED", error_message=str(exc))
        return published_count

    def process_new_comments(self) -> int:
        comments = self.ig.fetch_recent_comments(media_limit=5)
        replied_count = 0
        for c in comments:
            cid = c["comment_id"]
            username = c["username"]
            text = c["text"].strip()
            if not text or self.db.has_replied(cid):
                continue

            reply_text, meta = self.brain.generate_interaction_reply(text, user_handle=username, kind="COMMENT")
            self.ig.reply_to_comment(cid, reply_text)
            self.db.record_reply(
                cid,
                kind="COMMENT",
                user_handle=username,
                incoming_text=text,
                reply_text=reply_text,
                provider_used=f"{meta['provider']}:{meta['model']}",
                tokens_used=meta["total_tokens"],
            )
            logger.info("Replied to comment by @%s [%s | %d tokens]: %s", username, meta["provider"], meta["total_tokens"], reply_text)
            replied_count += 1
        return replied_count

    def handle_incoming_dm_webhook_event(self, webhook_payload: Dict[str, Any]) -> List[str]:
        replies_sent: List[str] = []
        for entry in webhook_payload.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message_obj = messaging_event.get("message", {})
                mid = message_obj.get("mid")
                text = message_obj.get("text", "").strip()

                if not sender_id or not mid or not text or message_obj.get("is_echo"):
                    continue
                if self.db.has_replied(mid):
                    continue

                reply_text, meta = self.brain.generate_interaction_reply(text, user_handle=sender_id, kind="DM")
                self.ig.send_direct_message(sender_id, reply_text)
                self.db.record_reply(
                    mid,
                    kind="DM",
                    user_handle=sender_id,
                    incoming_text=text,
                    reply_text=reply_text,
                    provider_used=f"{meta['provider']}:{meta['model']}",
                    tokens_used=meta["total_tokens"],
                )
                replies_sent.append(reply_text)
        return replies_sent


    def start_webhook_and_api_server(self, port: Optional[int] = None, background: bool = False) -> Optional[threading.Thread]:
        """
        Starts the live HTTP server for Meta Instagram Webhook verification & Online Control REST API.
        """
        listen_port = port or self.config.webhook_port
        orchestrator_ref = self

        class AgentHTTPHandler(http.server.BaseHTTPRequestHandler):
            def _allow_admin_request(self) -> bool:
                host = self.headers.get("Host", "")
                try:
                    hostname = urllib.parse.urlsplit("http://" + host).hostname
                except ValueError:
                    hostname = None
                origin = self.headers.get("Origin")
                if hostname not in ("localhost", "127.0.0.1", "::1") or (origin and origin not in ("http://" + host, "https://" + host)):
                    self._send_json(403, {"error": "Use the local dashboard through an SSH tunnel"})
                    return False
                return True

            def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:
                if not self._allow_admin_request():
                    return
                self.send_response(204)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.end_headers()

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)

                if parsed.path != "/webhook" and not self._allow_admin_request():
                    return

                if parsed.path in ("/", "/dashboard", "/dashboard/"):
                    root = Path(__file__).resolve().parent
                    if root.name == "src":
                        root = root.parent
                    try:
                        body = (root / "web" / "dashboard.html").read_bytes()
                    except OSError:
                        self._send_json(503, {"error": "Dashboard file unavailable; rerun the installer"})
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if parsed.path == "/webhook":
                    mode = query.get("hub.mode", [""])[0]
                    verify_token = query.get("hub.verify_token", [""])[0]
                    challenge = query.get("hub.challenge", [""])[0]
                    if mode == "subscribe" and orchestrator_ref.config.webhook_verify_token and verify_token == orchestrator_ref.config.webhook_verify_token:
                        logger.info("Meta Instagram Webhook verified successfully!")
                        resp_bytes = challenge.encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.send_header("Content-Length", str(len(resp_bytes)))
                        self.end_headers()
                        self.wfile.write(resp_bytes)
                    else:
                        self._send_json(403, {"error": "Invalid webhook verify_token"})
                    return

                if parsed.path in ("/health", "/api/status"):
                    saved_ig = orchestrator_ref.db.get_instagram_account()
                    self._send_json(
                        200,
                        {
                            "status": "ONLINE",
                            "agent": "آریا (Aria) — اولین اینفلوئنسر هوش مصنوعی ایران",
                            "webhook_endpoint": "/webhook",
                            "webhook_signature_configured": bool(orchestrator_ref.config.meta_app_secret),
                            "webhook_verify_token": orchestrator_ref.config.webhook_verify_token if parsed.path == "/api/status" else None,
                            "timezone": "Asia/Tehran",
                            "instagram_connected": bool(orchestrator_ref.config.ig_access_token and orchestrator_ref.config.ig_user_id),
                            "instagram_account": {
                                "ig_user_id": orchestrator_ref.config.ig_user_id,
                                "ig_username": saved_ig.get("ig_username", "") if saved_ig else "",
                                "ig_name": saved_ig.get("ig_name", "") if saved_ig else "",
                                "followers_count": saved_ig.get("followers_count", 0) if saved_ig else 0,
                                "media_count": saved_ig.get("media_count", 0) if saved_ig else 0,
                                "updated_at": saved_ig.get("updated_at", "") if saved_ig else "",
                            },
                            "token_report": orchestrator_ref.db.get_token_usage_report(),
                            "scheduled_media": orchestrator_ref.db.get_all_scheduled_media(limit=10),
                            "recent_replies": orchestrator_ref.db.get_recent_replies(limit=10),
                        },
                    )
                    return

                self._send_json(404, {"error": "Endpoint not found"})

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/webhook" and not self._allow_admin_request():
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self._send_json(400, {"error": "Invalid Content-Length"})
                    return
                if length < 0 or length > 1024 * 1024:
                    self._send_json(413, {"error": "Request body too large"})
                    return
                body_bytes = self.rfile.read(length)
                if parsed.path == "/webhook":
                    secret = orchestrator_ref.config.meta_app_secret
                    if not secret:
                        self._send_json(503, {"error": "META_APP_SECRET is not configured"})
                        return
                    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
                    supplied = self.headers.get("X-Hub-Signature-256", "")
                    if not hmac.compare_digest(supplied, expected):
                        self._send_json(403, {"error": "Invalid webhook signature"})
                        return
                try:
                    payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a JSON object")
                except (ValueError, UnicodeDecodeError):
                    self._send_json(400, {"error": "Invalid JSON object"})
                    return

                if parsed.path == "/webhook":
                    threading.Thread(
                        target=orchestrator_ref.handle_incoming_dm_webhook_event,
                        args=(payload,),
                        daemon=True,
                    ).start()
                    self._send_json(200, {"status": "EVENT_RECEIVED"})
                    return

                if parsed.path == "/api/connect-instagram":
                    try:
                        token = str(payload.get("access_token", "")).strip()
                        uid = str(payload.get("ig_user_id", "")).strip()
                        v_tok = str(payload.get("verify_token", orchestrator_ref.config.webhook_verify_token)).strip()
                        profile = orchestrator_ref.ig.discover_and_verify_account(access_token=token, ig_user_id=uid or None)
                        orchestrator_ref.db.save_instagram_account(
                            ig_user_id=str(profile.get("id", uid)),
                            access_token=token,
                            ig_username=str(profile.get("username", "")),
                            ig_name=str(profile.get("name", "")),
                            webhook_verify_token=v_tok,
                            followers_count=int(profile.get("followers_count", 0)),
                            media_count=int(profile.get("media_count", 0)),
                        )
                        orchestrator_ref.config.webhook_verify_token = v_tok
                        self._send_json(200, {"ok": True, "profile": profile})
                    except Exception as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                if parsed.path == "/api/add-key":
                    try:
                        if payload.get("provider") not in PROVIDER_DEFAULTS:
                            raise ValueError("Unknown AI provider")
                        if not str(payload.get("alias", "")).strip() or not str(payload.get("api_key", "")).strip():
                            raise ValueError("Alias and API key are required")
                        if int(payload.get("daily_limit", 500000)) <= 0:
                            raise ValueError("Daily token limit must be positive")
                        orchestrator_ref.db.upsert_api_key(
                            provider=str(payload["provider"]),
                            key_alias=str(payload["alias"]),
                            api_key=str(payload["api_key"]),
                            base_url=str(payload.get("base_url", "")),
                            scenario_model=str(payload.get("scenario_model", "")),
                            fast_model=str(payload.get("fast_model", "")),
                            daily_token_limit=int(payload.get("daily_limit", 500000)),
                            priority=int(payload.get("priority", 10)),
                        )
                        self._send_json(200, {"ok": True, "token_report": orchestrator_ref.db.get_token_usage_report()})
                    except Exception as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                if parsed.path == "/api/schedule-media":
                    try:
                        kind = str(payload.get("kind", ""))
                        if kind not in ("STORY_IMAGE", "STORY_VIDEO", "REEL"):
                            raise ValueError("Unsupported media kind")
                        media_url = str(payload.get("media_url", "")).strip()
                        media = urllib.parse.urlsplit(media_url)
                        if media.scheme != "https" or not media.hostname or media.username or media.password:
                            raise ValueError("A public HTTPS media URL is required")
                        publish_at = dt.datetime.fromisoformat(str(payload.get("publish_at", "")).replace("Z", "+00:00"))
                        tehran = ZoneInfo("Asia/Tehran")
                        if publish_at.tzinfo is None and payload.get("timezone") == "Asia/Tehran":
                            publish_at = publish_at.replace(tzinfo=tehran)
                        if publish_at.tzinfo is None:
                            raise ValueError("Publication time must include a UTC offset")
                        if publish_at <= dt.datetime.now(dt.timezone.utc):
                            raise ValueError("Publication time must be in the future")
                        publish_local = publish_at.astimezone(tehran).replace(tzinfo=None).isoformat(timespec="seconds")
                        row_id = orchestrator_ref.db.add_scheduled_media(kind, media_url, publish_local, str(payload.get("caption", "")))
                        self._send_json(200, {"ok": True, "schedule_id": row_id, "publish_at": publish_local, "timezone": "Asia/Tehran"})
                    except (ValueError, TypeError) as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                if parsed.path == "/api/cancel-schedule":
                    try:
                        row_id = int(payload.get("schedule_id", 0))
                        with orchestrator_ref.db._connect() as conn:
                            cur = conn.execute("UPDATE scheduled_media SET status = 'CANCELLED' WHERE id = ? AND status = 'PENDING'", (row_id,))
                            changed = cur.rowcount
                        if not changed:
                            self._send_json(409, {"ok": False, "error": "Schedule is missing or is no longer pending"})
                        else:
                            self._send_json(200, {"ok": True})
                    except (ValueError, TypeError):
                        self._send_json(400, {"ok": False, "error": "Invalid schedule ID"})
                    return

                if parsed.path == "/api/test-reply":
                    try:
                        reply_text, meta = orchestrator_ref.brain.generate_interaction_reply(
                            incoming_text=str(payload.get("text", "سلام آریا!")),
                            user_handle=str(payload.get("username", "user_test")),
                            kind=str(payload.get("kind", "DM")),
                        )
                        self._send_json(200, {"ok": True, "reply": reply_text, "meta": meta})
                    except Exception as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                if parsed.path == "/api/generate-daily":
                    try:
                        topic = str(payload.get("topic", "۲۴ ساعت زندگی من به عنوان هوش مصنوعی در تهران"))
                        pack = orchestrator_ref.brain.generate_daily_content_pack(topic)
                        self._send_json(200, {"ok": True, "pack": pack})
                    except Exception as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                self._send_json(404, {"error": "Endpoint not found"})

            def log_message(self, fmt: str, *args: Any) -> None:
                logger.info("HTTP %s - " + fmt, self.address_string(), *args)

        server = http.server.ThreadingHTTPServer((self.config.webhook_host, listen_port), AgentHTTPHandler)
        logger.info("Aria Online Webhook & Control Server listening on http://%s:%d (Webhook: /webhook, Status: /api/status)", self.config.webhook_host, listen_port)
        if background:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            return t
        server.serve_forever()
        return None

    def run_daemon(self) -> None:
        self.start_webhook_and_api_server(background=True)
        logger.info(
            "Starting Iran's First AI Influencer Agent Daemon (provider=%s, poll=%ss)...",
            self.config.preferred_provider,
            self.config.poll_interval_seconds,
        )
        while True:
            try:
                if self.config.ig_access_token and self.config.ig_user_id:
                    self.process_due_schedules()
                    self.process_new_comments()
            except Exception as exc:
                logger.error("Daemon cycle error: %s", exc)
            time.sleep(self.config.poll_interval_seconds)


# ============================================================================
# 8. CLI ENTRYPOINT & DEMO MODE
# ============================================================================


def run_demo_mode(
    config: AgentConfig,
    bg_image_path: Optional[str] = None,
    output_mp4: str = "demo_ai_influencer_story.mp4",
) -> None:
    """
    Runs an offline self-test:
    1. Registers sample multi-AI provider profiles in SQLite (`gemini`, `openai`, `deepseek`, `openrouter`, `custom_avalai`)
    2. Simulates token logging & daily budget tracking across tasks
    3. Renders a 9:16 MP4 motion story with RTL Persian text (Vazirmatn / Unified Fallback)
    """
    logger.info("Running Multi-AI Router & Token Manager Demo Mode...")
    db = StateDatabase(config.db_path)

    # Seed sample multi-provider entries if vault is empty so user can see how the vault & token report work
    existing = db.get_token_usage_report()["configured_keys"]
    if not existing:
        db.upsert_api_key("gemini", "gemini_primary", "AIzaSyDEMO_KEY_1111", daily_token_limit=500000, priority=10)
        db.upsert_api_key("openai", "openai_gpt4o", "sk-proj-DEMO_KEY_2222", daily_token_limit=300000, priority=20)
        db.upsert_api_key("deepseek", "deepseek_economical", "sk-ds-DEMO_KEY_3333", daily_token_limit=1000000, priority=30)
        db.upsert_api_key("anthropic", "claude_creative", "sk-ant-DEMO_KEY_4444", daily_token_limit=250000, priority=40)
        db.upsert_api_key(
            "custom",
            "iran_gateway_avalai",
            "aa-DEMO_KEY_5555",
            base_url="https://api.avalai.ir/v1",
            scenario_model="gpt-4o",
            fast_model="gpt-4o-mini",
            daily_token_limit=400000,
            priority=50,
        )
        db.log_token_usage("gemini", "gemini_primary", "gemini-2.5-pro", "SCENARIO_PACK", 620, 980, "SUCCESS")
        db.log_token_usage("deepseek", "deepseek_economical", "deepseek-chat", "DM_REPLY", 210, 85, "SUCCESS")
        db.log_token_usage("openai", "openai_gpt4o", "gpt-4o-mini", "COMMENT_REPLY", 180, 64, "SUCCESS")

    StoryMediaGenerator.render_futuristic_motion_story(
        output_mp4_path=output_mp4,
        headline_fa="سلام ایران! من «آریا» هستم؛ اولین هوش مصنوعی ایران",
        subheadline_fa="تو دایرکت بگو چه کاری رو برات هوشمند کنم؟ (آنلاین ۲۴/۷)",
        badge_text_fa="آنلاین ۲۴/۷ // استودیوی ابری تهران (Node 01)",
        background_image_path=bg_image_path,
        duration_sec=4,
        fps=24,
    )
    report = db.get_token_usage_report()
    demo_summary = {
        "persona": "آریا (اولین اینفلوئنسر مجازی هوش مصنوعی ایران)",
        "encoding_and_typography": "UTF-8 | RTL | Vazirmatn + Unified Persian/Latin Fallback",
        "supported_ai_providers": list(PROVIDER_DEFAULTS.keys()) + ["elevenlabs_tts"],
        "token_management_report": report,
        "generated_motion_story_file": output_mp4,
    }
    print(json.dumps(demo_summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Instagram AI Influencer Agent with Multi-AI Token Manager")
    parser.add_argument("--demo", action="store_true", help="Run self-test, seed demo token report & render 9:16 motion story MP4")
    parser.add_argument("--bg-image", type=str, default=None, help="Optional background portrait for motion story")
    parser.add_argument("--output-mp4", type=str, default="demo_ai_influencer_story.mp4", help="Output MP4 path for demo")

    # Multi-AI Key & Token Management CLI flags
    parser.add_argument(
        "--provider",
        choices=["auto", "gemini", "openai", "anthropic", "deepseek", "openrouter", "custom"],
        default=os.getenv("AI_PROVIDER", "auto"),
        help="Preferred AI provider ('auto' enables smart priority routing & failover across all keys)",
    )
    parser.add_argument("--add-key", action="store_true", help="Add or update an AI provider API key in the SQLite vault")
    parser.add_argument("--alias", type=str, help="Unique alias for the key (e.g., 'gemini_main', 'openai_backup', 'avalai_ir')")
    parser.add_argument("--api-key", type=str, help="The API key string")
    parser.add_argument("--base-url", type=str, default="", help="Optional custom Base URL (for OpenRouter, AvalAI, GapGPT, Ollama)")
    parser.add_argument("--scenario-model", type=str, default="", help="Model for heavy scenario writing (e.g., gpt-4o, gemini-2.5-pro)")
    parser.add_argument("--fast-model", type=str, default="", help="Fast model for DMs/comments (e.g., gpt-4o-mini, deepseek-chat)")
    parser.add_argument("--daily-limit", type=int, default=500000, help="Daily token budget limit for this key")
    parser.add_argument("--priority", type=int, default=10, help="Failover priority (lower number = higher priority)")
    parser.add_argument("--token-report", action="store_true", help="Display configured API keys and today's token usage report")

    # Content & Instagram Operations CLI flags
    parser.add_argument("--generate-daily", action="store_true", help="Generate daily scenario, caption & stories")
    parser.add_argument("--topic", type=str, default="معرفی خودم به عنوان اولین اینفلوئنسر هوش مصنوعی ایران", help="Topic for daily generation")
    parser.add_argument("--schedule-story", action="store_true", help="Queue a story for scheduled publication")
    parser.add_argument("--media-url", type=str, help="Public HTTPS URL of story image or MP4 video")
    parser.add_argument("--media-type", choices=["IMAGE", "VIDEO"], default="IMAGE", help="Story media type")
    parser.add_argument("--publish-at", type=str, help="ISO timestamp e.g. 2026-10-19T20:00:00")
    parser.add_argument("--connect-ig", action="store_true", help="Connect & verify Instagram Business/Creator Account via Meta Graph API")
    parser.add_argument("--ig-token", type=str, default="", help="Instagram Graph API Access Token (EAA...)")
    parser.add_argument("--ig-user-id", type=str, default="", help="Instagram Business Account ID (optional; auto-discovered if omitted)")
    parser.add_argument("--run-server", action="store_true", help="Run HTTP Webhook & Online Control API server only")
    parser.add_argument("--port", type=int, default=int(os.getenv("AGENT_WEBHOOK_PORT", "8080")), help="Port for HTTP Webhook & API server (default: 8080)")
    parser.add_argument("--run-daemon", action="store_true", help="Run 24/7 scheduler, comment/DM responder, and HTTP Webhook server")

    args = parser.parse_args()
    config = AgentConfig(preferred_provider=args.provider)

    if args.demo:
        run_demo_mode(config=config, bg_image_path=args.bg_image, output_mp4=args.output_mp4)
        return

    orchestrator = InstagramAgentOrchestrator(config)

    if args.add_key:
        if not args.alias or not args.api_key or args.provider == "auto":
            parser.error("--add-key نیازمند مشخص کردن --provider (غیر از auto)، --alias و --api-key است.")
        orchestrator.db.upsert_api_key(
            provider=args.provider,
            key_alias=args.alias,
            api_key=args.api_key,
            base_url=args.base_url,
            scenario_model=args.scenario_model,
            fast_model=args.fast_model,
            daily_token_limit=args.daily_limit,
            priority=args.priority,
        )
        logger.info("Saved API key '%s' for provider '%s' (daily limit: %d tokens)", args.alias, args.provider, args.daily_limit)
        print(json.dumps(orchestrator.db.get_token_usage_report(), ensure_ascii=False, indent=2))
    elif args.token_report:
        print(json.dumps(orchestrator.db.get_token_usage_report(), ensure_ascii=False, indent=2))
    elif args.generate_daily:
        pack = orchestrator.brain.generate_daily_content_pack(args.topic)
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    elif args.schedule_story:
        if not args.media_url or not args.publish_at:
            parser.error("--schedule-story نیازمند --media-url و --publish-at است.")
        kind = "STORY_VIDEO" if args.media_type == "VIDEO" else "STORY_IMAGE"
        row_id = orchestrator.db.add_scheduled_media(kind=kind, media_url=args.media_url, publish_at=args.publish_at)
        logger.info("Scheduled %s #%d for %s", kind, row_id, args.publish_at)
    elif args.connect_ig:
        token = args.ig_token or config.ig_access_token
        uid = args.ig_user_id or config.ig_user_id
        profile = orchestrator.ig.discover_and_verify_account(access_token=token, ig_user_id=uid or None)
        orchestrator.db.save_instagram_account(
            ig_user_id=str(profile.get("id", uid)),
            access_token=token,
            ig_username=str(profile.get("username", "")),
            ig_name=str(profile.get("name", "")),
            webhook_verify_token=config.webhook_verify_token,
            followers_count=int(profile.get("followers_count", 0)),
            media_count=int(profile.get("media_count", 0)),
        )
        logger.info("Successfully connected Instagram account @%s (ID: %s)", profile.get("username"), profile.get("id"))
        print(json.dumps({"connected": True, "profile": profile}, ensure_ascii=False, indent=2))
    elif args.run_server:
        orchestrator.start_webhook_and_api_server(port=args.port, background=False)
    elif args.run_daemon:
        config.webhook_port = args.port
        orchestrator.run_daemon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
