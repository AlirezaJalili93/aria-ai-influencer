"""Dashboard -> HTTP API -> fake local AI provider -> persistent SQLite."""
import datetime as dt
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class FakeAI(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        content = json.dumps({'topic': 'offline', 'caption': {'text_fa': 'کپشن آزمایشی'}, 'scheduled_stories': []}, ensure_ascii=False) if payload.get('response_format') else 'پاسخ آزمایشی از سرویس محلی'
        body = json.dumps({'choices': [{'message': {'content': content}}], 'usage': {'prompt_tokens': 12, 'completion_tokens': 13}}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeAI)
        threading.Thread(target=cls.provider.serve_forever, daemon=True).start()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and not k.startswith('IG_') and not k.startswith('AGENT_')}
        env.update(IG_ACCESS_TOKEN='', IG_USER_ID='', META_APP_SECRET='', AI_PROVIDER='auto', AGENT_DB_PATH=str(Path(cls.temp.name) / 'state.db'), AGENT_WEBHOOK_HOST='127.0.0.1', AGENT_WEBHOOK_PORT=str(cls.port), TZ='Asia/Tehran')
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / 'instagram_ai_agent.py'), '--run-server'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cls.base = f'http://127.0.0.1:{cls.port}'
        for _ in range(80):
            try:
                with urllib.request.urlopen(cls.base + '/health', timeout=1):
                    break
            except OSError:
                if cls.proc.poll() is not None:
                    raise RuntimeError(cls.proc.stderr.read().decode())
                time.sleep(.1)
        else:
            raise RuntimeError('Dashboard server startup timeout')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.proc.stderr.close()
        cls.provider.shutdown()
        cls.provider.server_close()
        cls.temp.cleanup()

    def request(self, path, data=None, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json', **(headers or {})})
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def test_dashboard_served_and_admin_origin_checked(self):
        for path in ['/', '/dashboard', '/dashboard/']:
            with urllib.request.urlopen(self.base + path) as response:
                self.assertIn('text/html', response.headers['Content-Type'])
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertIn('frame-ancestors', response.headers['Content-Security-Policy'])
                self.assertIn('داشبورد مدیریت', response.read().decode())
        for headers in [{'Host': 'attacker.invalid'}, {'Origin': 'https://attacker.invalid'}]:
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.request('/api/status', headers=headers)
            self.assertEqual(err.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.request('/api/add-key', {'provider': 'fake', 'alias': 'x', 'api_key': 'x'})
        self.assertEqual(err.exception.code, 400)

    def test_real_api_key_reply_generation_schedule_and_cancel(self):
        key = 'offline-secret-key-12345'
        saved = self.request('/api/add-key', {'provider': 'custom', 'alias': 'qa_custom', 'api_key': key, 'base_url': f'http://127.0.0.1:{self.provider.server_port}', 'scenario_model': 'fake-scenario', 'fast_model': 'fake-fast', 'daily_limit': 1000})
        self.assertTrue(saved['ok'])
        self.assertNotIn(key, json.dumps(saved))
        reply = self.request('/api/test-reply', {'text': 'سلام'})
        self.assertEqual(reply['reply'], 'پاسخ آزمایشی از سرویس محلی')
        self.assertEqual(reply['meta']['total_tokens'], 25)
        pack = self.request('/api/generate-daily', {'topic': 'offline'})
        self.assertEqual(pack['pack']['caption']['text_fa'], 'کپشن آزمایشی')
        when = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
        scheduled = self.request('/api/schedule-media', {'kind': 'REEL', 'media_url': 'https://example.invalid/video.mp4', 'publish_at': when, 'caption': 'test'})
        self.assertTrue(scheduled['ok'])
        row_id = scheduled['schedule_id']
        status = self.request('/api/status')
        self.assertEqual(status['scheduled_media'][0]['id'], row_id)
        self.assertEqual(status['token_report']['configured_keys'][0]['used_tokens_today'], 50)
        self.assertTrue(self.request('/api/cancel-schedule', {'schedule_id': row_id})['ok'])
        self.assertEqual(self.request('/api/status')['scheduled_media'][0]['status'], 'CANCELLED')
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.request('/api/cancel-schedule', {'schedule_id': row_id})
        self.assertEqual(err.exception.code, 409)
        for values in [dict(kind='INVALID', media_url='https://example.invalid/a'), dict(kind='REEL', media_url='http://example.invalid/a')]:
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.request('/api/schedule-media', dict(publish_at=when, **values))
            self.assertEqual(err.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
