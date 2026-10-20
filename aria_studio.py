# -*- coding: utf-8 -*-
"""Persistent studio, character resources and daily draft production.

The original Gemini UI is retained in docs/reference. Publication remains in the
existing Instagram queue; a local draft is never treated as published media.
"""
import base64
import datetime as dt
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
TEHRAN = ZoneInfo('Asia/Tehran')
OPENAI_VOICES = ('alloy', 'ash', 'ballad', 'coral', 'echo', 'fable', 'nova', 'onyx', 'sage', 'shimmer', 'verse', 'marin', 'cedar')


def read_profile():
    return json.loads((ROOT / 'character/aria.json').read_text(encoding='utf-8'))


class StudioRuntime:
    def __init__(self, agent, renderer):
        self.agent, self.db, self.renderer = agent, agent.db, renderer
        self.media_dir = Path(agent.config.db_path).resolve().parent / 'media'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.media_lock = threading.Lock()
        self.voice_lock = threading.Lock()
        with self.db._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS studio_settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS content_packs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, topic TEXT NOT NULL, pack_json TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS studio_drafts (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, value TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS studio_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, result TEXT NOT NULL, updated_at TEXT NOT NULL)')
        self.defaults = dict(enabled=True, time='09:00', provider='auto', topic='یک موضوع تازه از زندگی آریا در تهران و یک ترفند کاربردی AI؛ ادعای خبر یا ترند تأییدنشده نکن.', generate_image=False)
        voice = read_profile()['voice']
        self.defaults.update(voice=os.getenv('OPENAI_TTS_VOICE', voice['voice']),
                             voice_speed=voice['speed'], voice_instructions=voice['instructions'])

    def settings(self):
        with self.db._connect() as conn:
            row = conn.execute('SELECT value FROM studio_settings WHERE id=1').fetchone()
        return {**self.defaults, **(json.loads(row[0]) if row else {})}

    def state(self):
        with self.db._connect() as conn:
            packs = [dict(r) for r in conn.execute('SELECT * FROM content_packs ORDER BY created_at DESC LIMIT 10')]
            drafts = [json.loads(r[0]) for r in conn.execute('SELECT value FROM studio_drafts ORDER BY created_at DESC LIMIT 20')]
            jobs = [dict(r) for r in conn.execute('SELECT * FROM studio_jobs ORDER BY updated_at DESC LIMIT 10')]
        for p in packs:
            p['pack'] = json.loads(p.pop('pack_json'))
        for j in jobs:
            j['result'] = json.loads(j['result'])
        return dict(ok=True, character=read_profile(), settings=self.settings(), packs=packs, drafts=drafts, jobs=jobs,
                    media_capabilities=dict(motion=True, voice_configured=self.has_openai_key(), image_configured=self.has_openai_key(),
                                            voice_provider='openai', voice_model=self.voice_model(), voice_options=list(OPENAI_VOICES)),
                    reference=dict(original_video_retrieved=False, original_video='aria_motion_story_day1.mp4', original_dashboard='docs/reference/gemini-studio-dom.html'))

    def save_pack(self, topic, provider=None):
        pack = self.agent.brain.generate_daily_content_pack(topic, preferred_provider=provider)
        pack_id = uuid.uuid4().hex
        with self.db._connect() as conn:
            conn.execute('INSERT INTO content_packs VALUES(?,?,?,?)', (pack_id, dt.datetime.now(TEHRAN).isoformat(), topic, json.dumps(pack, ensure_ascii=False)))
        return pack, pack_id

    def _job(self, job_id, status, result):
        with self.db._connect() as conn:
            conn.execute('INSERT OR REPLACE INTO studio_jobs VALUES(?,?,?,?)', (job_id, status, json.dumps(result, ensure_ascii=False), dt.datetime.now(TEHRAN).isoformat()))

    def daily_tick(self, now=None):
        now = now or dt.datetime.now(TEHRAN)
        cfg = self.settings()
        if not cfg['enabled'] or now.strftime('%H:%M') < cfg['time'] or not self.db.get_candidate_keys(cfg['provider']):
            return False
        job_id = 'daily:' + now.date().isoformat()
        with self.db._connect() as conn:
            claimed = conn.execute('INSERT OR IGNORE INTO studio_jobs VALUES(?,?,?,?)', (job_id, 'RUNNING', '{}', now.isoformat())).rowcount
        if not claimed:
            return False
        try:
            pack, pack_id = self.save_pack(cfg['topic'], cfg['provider'])
            result = {'pack_id': pack_id}
            if cfg['generate_image']:
                try:
                    result['image'] = self.generate_image(pack.get('topic', cfg['topic']))
                except Exception as exc:
                    result['image_error'] = str(exc)
            self._job(job_id, 'DONE', result)
        except Exception as exc:
            self._job(job_id, 'FAILED', {'error': str(exc)})
        return True

    def generate_image(self, prompt):
        keys = [k for k in self.db.get_candidate_keys('openai') if k['provider'] == 'openai']
        if not keys:
            raise ValueError('برای تولید تصویر، کلید فعال OpenAI با بودجه باقی‌مانده ثبت کنید.')
        key = keys[0]
        model = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-1')
        data = json.dumps(dict(model=model, prompt=read_profile()['visual_seed_prompt_en'] + '\nVertical story composition, no text. Scene: ' + prompt, size='1024x1536', n=1), ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(key['base_url'].rstrip('/') + '/images/generations', data=data, headers={'Authorization':'Bearer '+key['api_key'], 'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.load(response)
        raw = base64.b64decode(result['data'][0]['b64_json'], validate=True)
        filename = uuid.uuid4().hex + '.png'
        with Image.open(io.BytesIO(raw)) as image:
            ImageOps.fit(image.convert('RGB'), (1080,1920)).save(self.media_dir / filename)
        usage = result.get('usage', {})
        self.db.log_token_usage('openai', key['key_alias'], model, 'IMAGE_GENERATION', int(usage.get('input_tokens', 0)), int(usage.get('output_tokens', 0)))
        self._job(filename[:-4], 'DONE', {'media_url':'/media/'+filename, 'media_type':'image'})
        return '/media/' + filename

    def has_openai_key(self):
        return any(k['provider'] == 'openai' for k in self.db.get_candidate_keys('openai'))

    def voice_model(self):
        return os.getenv('OPENAI_TTS_MODEL') or read_profile()['voice']['model']

    def generate_voice(self, payload):
        text = str(payload.get('text', '')).strip()
        if not text or len(text) > 4096:
            raise ValueError('متن صدا باید بین ۱ تا ۴۰۹۶ نویسه باشد.')
        cfg = self.settings()
        voice = str(payload.get('voice', cfg['voice']))
        instructions = str(payload.get('instructions', cfg['voice_instructions'])).strip()
        speed = payload.get('speed', cfg['voice_speed'])
        if isinstance(speed, bool):
            raise ValueError('سرعت صدا باید بین ۰٫۲۵ تا ۴ باشد.')
        try:
            speed = float(speed)
        except (ValueError, TypeError):
            raise ValueError('سرعت صدا باید بین ۰٫۲۵ تا ۴ باشد.') from None
        if not math.isfinite(speed) or not 0.25 <= speed <= 4:
            raise ValueError('سرعت صدا باید بین ۰٫۲۵ تا ۴ باشد.')
        if voice not in OPENAI_VOICES:
            raise ValueError('یکی از صداهای OpenAI را انتخاب کنید.')
        if not instructions or len(instructions) > 2000:
            raise ValueError('راهنمای لحن باید بین ۱ تا ۲۰۰۰ نویسه باشد.')
        keys = [k for k in self.db.get_candidate_keys('openai') if k['provider'] == 'openai']
        if not keys:
            raise ValueError('برای ساخت صدا، یک کلید فعال OpenAI در مدیریت کلیدها ثبت کنید؛ ElevenLabs لازم نیست.')
        key, model = keys[0], self.voice_model()
        data = dict(model=model, voice=voice, input=text, response_format='mp3', speed=speed)
        if model not in ('tts-1', 'tts-1-hd'):
            data['instructions'] = instructions
        if not self.voice_lock.acquire(blocking=False):
            return 409, dict(ok=False, error='یک صدا در حال تولید است؛ تا پایان آن منتظر بمانید.')
        job_id = uuid.uuid4().hex
        destination = self.media_dir / (job_id + '.mp3')
        try:
            self._job(job_id, 'RUNNING', {'media_type': 'voice', 'provider': 'openai', 'model': model, 'voice': voice})
            try:
                req = urllib.request.Request(key['base_url'].rstrip('/') + '/audio/speech',
                                             data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                                             headers={'Authorization': 'Bearer ' + key['api_key'], 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'}, method='POST')
                with urllib.request.urlopen(req, timeout=90) as response:
                    content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    audio = response.read(20 * 1024 * 1024 + 1)
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                raise RuntimeError('OpenAI ساخت صدا را نپذیرفت (HTTP %s). اعتبار کلید، دسترسی مدل و اعتبار مالی حساب API را بررسی کنید.' % code) from None
            except OSError:
                raise RuntimeError('ارتباط با سرویس صدای OpenAI برقرار نشد. اتصال شبکه و نشانی سرویس را بررسی کنید.') from None
            except Exception:
                raise RuntimeError('درخواست ساخت صدای OpenAI انجام نشد؛ تنظیمات کلید و سرویس را بررسی کنید.') from None
            if content_type not in ('audio/mpeg', 'audio/mp3', 'application/octet-stream') or not audio or len(audio) > 20 * 1024 * 1024:
                raise RuntimeError('سرویس OpenAI فایل MP3 معتبر با اندازهٔ مجاز برنگرداند.')
            if not (audio.startswith(b'ID3') or (len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224)):
                raise RuntimeError('پاسخ سرویس فایل MP3 نیست؛ فایل صدا ذخیره نشد.')
            destination.write_bytes(audio)
            # Merge only voice preferences into the latest settings: retain concurrent daily changes.
            with self.db._connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT value FROM studio_settings WHERE id=1').fetchone()
                saved = json.loads(row[0]) if row else {}
                saved.update(voice=voice, voice_speed=speed, voice_instructions=instructions)
                conn.execute('INSERT OR REPLACE INTO studio_settings VALUES(1,?)', (json.dumps(saved, ensure_ascii=False),))
            result = dict(media_url='/media/' + destination.name, media_type='voice', provider='openai', model=model,
                          voice=voice, speed=speed, text_characters=len(text), usage_reported=False, ai_generated=True)
            # /audio/speech returns binary MP3, not token usage. Do not invent usage/cost numbers.
            self._job(job_id, 'DONE', result)
            return 200, dict(ok=True, **result)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            self._job(job_id, 'FAILED', {'media_type': 'voice', 'provider': 'openai', 'error': str(exc)})
            raise
        finally:
            self.voice_lock.release()

    def handle_post(self, path, payload):
        if path == '/api/studio-settings':
            cfg = self.settings()
            for key in ('enabled','generate_image'):
                if key in payload:
                    if not isinstance(payload[key], bool): raise ValueError('Boolean expected: '+key)
                    cfg[key] = payload[key]
            time = str(payload.get('time',cfg['time']))
            dt.datetime.strptime(time,'%H:%M')
            cfg.update(time=time, topic=str(payload.get('topic',cfg['topic']))[:4000], provider=str(payload.get('provider',cfg['provider'])))
            if cfg['provider'] not in ('auto','gemini','openai','anthropic','deepseek','openrouter','custom'): raise ValueError('Unknown provider')
            with self.db._connect() as conn:
                conn.execute('INSERT OR REPLACE INTO studio_settings VALUES(1,?)',(json.dumps(cfg,ensure_ascii=False),))
            return 200, dict(ok=True, settings=cfg)
        if path == '/api/toggle-key':
            if not isinstance(payload.get('active'), bool): raise ValueError('active must be boolean')
            with self.db._connect() as conn:
                changed = conn.execute('UPDATE api_keys_vault SET is_active=? WHERE key_alias=?',(int(payload['active']), str(payload.get('alias','')))).rowcount
            if not changed: raise ValueError('Key alias not found')
            return 200, dict(ok=True)
        if path == '/api/save-draft':
            draft = {k:str(payload.get(k,''))[:4000] for k in ('headline','subheadline','badge','caption','slot','sticker')}
            draft.update(id=uuid.uuid4().hex, created_at=dt.datetime.now(TEHRAN).isoformat(), status='DRAFT')
            if payload.get('image'):
                encoded = str(payload['image'])
                if not encoded.startswith('data:image/png;base64,'): raise ValueError('PNG data URL required')
                raw = base64.b64decode(encoded.split(',',1)[1], validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.size != (1080,1920): raise ValueError('Story must be 1080x1920')
                    image.verify()
                filename = draft['id']+'.png'
                (self.media_dir / filename).write_bytes(raw)
                draft['media_url']='/media/'+filename
            with self.db._connect() as conn:
                conn.execute('INSERT INTO studio_drafts VALUES(?,?,?)',(draft['id'],draft['created_at'],json.dumps(draft,ensure_ascii=False)))
            return 200, dict(ok=True,draft=draft)
        if path == '/api/generate-image':
            return 200, dict(ok=True,media_url=self.generate_image(str(payload.get('prompt','استودیوی ابری تهران'))[:4000]))
        if path == '/api/generate-voice':
            return self.generate_voice(payload)
        if path == '/api/render-motion':
            background = ROOT/'assets/reference/aria-story.jpg'
            selected = str(payload.get('background_image', ''))
            if selected.startswith('/media/'):
                candidate = (self.media_dir / selected[7:]).resolve()
                if candidate.parent != self.media_dir.resolve() or candidate.suffix.lower() not in ('.png','.jpg') or not candidate.is_file():
                    raise ValueError('Invalid local background image')
                background = candidate
            if not self.media_lock.acquire(blocking=False):
                return 409, dict(ok=False,error='یک رندر در حال اجراست. تا پایان آن منتظر بمانید.')
            job_id=uuid.uuid4().hex
            self._job(job_id,'RUNNING',{})
            def work():
                try:
                    name=job_id+'.mp4'
                    self.renderer.render_futuristic_motion_story(str(self.media_dir/name), headline_fa=str(payload.get('headline','سلام ایران! من آریا هستم'))[:160],subheadline_fa=str(payload.get('subheadline','چه کاری رو برات هوشمند کنم؟'))[:220],badge_text_fa=str(payload.get('badge','استودیوی ابری تهران (Node 01)'))[:120],background_image_path=str(background))
                    # The original renderer writes MPEG-4 Part 2. Prefer H.264 when ffmpeg is available.
                    if shutil.which('ffmpeg'):
                        converted=self.media_dir/(job_id+'-h264.mp4')
                        subprocess.run(['ffmpeg','-y','-i',str(self.media_dir/name),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(converted)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
                        converted.replace(self.media_dir/name)
                    self._job(job_id,'DONE',{'media_url':'/media/'+name, 'media_type':'motion'})
                except Exception as exc:
                    self._job(job_id,'FAILED',{'error':str(exc)})
                finally:self.media_lock.release()
            threading.Thread(target=work,daemon=True).start()
            return 202, dict(ok=True,job_id=job_id)
        return None
