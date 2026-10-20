"""OpenAI speech routing and persistence without real API keys or paid calls."""
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import instagram_ai_agent as agent
from aria_studio import read_profile

FAKE_MP3 = b'ID3\x04\x00\x00\x00\x00\x00\x00offline-audio-fixture'


class SpeechGateway(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.requests.append((self.path, self.headers.get('Authorization'),
                                     json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        self.send_response(self.server.status)
        self.send_header('Content-Type', self.server.content_type)
        self.send_header('Content-Length', str(len(self.server.audio)))
        self.end_headers()
        self.wfile.write(self.server.audio)

    def log_message(self, *args):
        pass


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        clear = {v['env_key']: '' for v in agent.PROVIDER_DEFAULTS.values()}
        clear.update(OPENAI_TTS_MODEL='', OPENAI_TTS_VOICE='cedar')
        self.env = patch.dict(os.environ, clear)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config = agent.AgentConfig(db_path=str(Path(self.temp.name) / 'state.db'), ig_access_token='', ig_user_id='')
        self.app = agent.InstagramAgentOrchestrator(self.config)
        self.gateway = http.server.ThreadingHTTPServer(('127.0.0.1', 0), SpeechGateway)
        self.gateway.requests = []
        self.gateway.status = 200
        self.gateway.content_type = 'audio/mpeg'
        self.gateway.audio = FAKE_MP3
        self.worker = threading.Thread(target=self.gateway.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop_gateway)
        self.base = 'http://127.0.0.1:%d/v1' % self.gateway.server_port

    def stop_gateway(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.worker.join(timeout=5)

    def add_openai(self, alias='speech', **kwargs):
        self.app.db.upsert_api_key('openai', alias, 'offline-openai-key', base_url=self.base, **kwargs)

    def generate(self, **kwargs):
        return self.app.studio.handle_post('/api/generate-voice', {'text': 'سلام ایران! من آریا هستم.', **kwargs})

    def test_openai_key_sends_persian_character_prompt_and_saves_mp3(self):
        self.app.db.upsert_api_key('custom', 'wrong-provider', 'wrong-key', base_url=self.base, priority=1)
        self.add_openai(priority=20)
        code, result = self.generate()
        self.assertEqual(code, 200)
        path, auth, payload = self.gateway.requests[0]
        self.assertEqual(path, '/v1/audio/speech')
        self.assertEqual(auth, 'Bearer offline-openai-key')
        self.assertEqual(payload['model'], 'gpt-4o-mini-tts')
        self.assertEqual(payload['voice'], 'cedar')
        self.assertEqual(payload['response_format'], 'mp3')
        self.assertEqual(payload['input'], 'سلام ایران! من آریا هستم.')
        self.assertEqual(payload['instructions'], read_profile()['voice']['instructions'])
        self.assertEqual((self.app.studio.media_dir / result['media_url'].split('/')[-1]).read_bytes(), FAKE_MP3)
        self.assertFalse(result['usage_reported'])
        self.assertTrue(result['ai_generated'])
        self.assertNotIn('offline-openai-key', json.dumps(result))
        self.assertEqual(self.app.studio.state()['jobs'][0]['status'], 'DONE')
        # Binary speech responses must not create invented token usage entries.
        with self.app.db._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM token_usage_logs').fetchone()[0], 0)

    def test_voice_preferences_and_download_survive_restart(self):
        self.add_openai()
        self.app.studio.handle_post('/api/studio-settings', {'enabled': False, 'topic': 'موضوع ذخیره‌شده'})
        self.generate(voice='marin', speed=0.9, instructions='صمیمی و با تلفظ روشن فارسی صحبت کن.')
        restarted = agent.InstagramAgentOrchestrator(self.config)
        state = restarted.studio.state()
        self.assertEqual(state['settings']['voice'], 'marin')
        self.assertEqual(state['settings']['voice_speed'], 0.9)
        self.assertFalse(state['settings']['enabled'])
        self.assertEqual(state['settings']['topic'], 'موضوع ذخیره‌شده')
        restarted.studio.handle_post('/api/generate-voice', {'text': 'دوباره سلام'})
        self.assertEqual(self.gateway.requests[-1][2]['voice'], 'marin')
        self.assertEqual(self.gateway.requests[-1][2]['instructions'], 'صمیمی و با تلفظ روشن فارسی صحبت کن.')
        self.assertTrue((restarted.studio.media_dir / state['jobs'][0]['result']['media_url'].split('/')[-1]).is_file())

    def test_no_openai_or_paused_or_exhausted_key_never_calls_provider(self):
        self.app.db.upsert_api_key('custom', 'custom', 'wrong-key')
        with self.assertRaisesRegex(ValueError, 'OpenAI'):
            self.generate()
        self.add_openai(daily_token_limit=10)
        self.app.studio.handle_post('/api/toggle-key', {'alias': 'speech', 'active': False})
        self.assertFalse(self.app.studio.state()['media_capabilities']['voice_configured'])
        with self.assertRaises(ValueError):
            self.generate()
        self.app.studio.handle_post('/api/toggle-key', {'alias': 'speech', 'active': True})
        self.app.db.log_token_usage('openai', 'speech', 'fake', 'DM_REPLY', 5, 5)
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.gateway.requests, [])

    def test_input_limits_are_validated_before_any_paid_call(self):
        self.add_openai()
        for payload in [dict(text=''), dict(text='آ' * 4097), dict(voice='invalid'),
                        dict(speed=True), dict(speed='bad'), dict(speed=float('nan')),
                        dict(speed=0.2), dict(speed=4.1), dict(instructions=''),
                        dict(instructions='a' * 2001)]:
            with self.subTest(payload=str(payload)[:60]), self.assertRaises(ValueError):
                self.generate(**payload)
        self.assertEqual(self.gateway.requests, [])

    def test_provider_error_is_recorded_without_key_leak_or_retry(self):
        self.add_openai()
        self.gateway.status = 401
        self.gateway.content_type = 'application/json'
        self.gateway.audio = b'{"error":"Incorrect API key: offline-openai-key"}'
        status, result = self.generate()
        self.assertEqual(status, 502)
        self.assertEqual(result['provider_status'], 401)
        self.assertIn('HTTP 401', result['error'])
        self.assertNotIn('offline-openai-key', json.dumps(result))
        jobs = self.app.studio.state()['jobs']
        self.assertEqual(jobs[0]['status'], 'FAILED')
        self.assertNotIn('offline-openai-key', json.dumps(jobs))
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(list(self.app.studio.media_dir.iterdir()), [])

    def test_429_distinguishes_credit_quota_spend_and_rate_limits_without_retry(self):
        self.add_openai()
        self.gateway.status, self.gateway.content_type = 429, 'application/json'
        cases = {
            'credit_balance_exhausted': 'پیش‌پرداخت',
            'insufficient_quota': 'سهمیه',
            'organization_spend_limit_exceeded': 'هزینهٔ سازمان',
            'project_spend_limit_exceeded': 'هزینهٔ پروژه',
            'organization_usage_limit_exceeded': 'مصرف مجاز سازمان',
            'rate_limit_exceeded': 'بازهٔ زمانی',
            'slow_down': 'سرعت افزایش',
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.gateway.audio = json.dumps({'error': {'code': code, 'type': 'insufficient_quota',
                                                          'message': 'offline-openai-key'}}).encode()
                status, result = self.generate()
                self.assertEqual(status, 429)
                self.assertEqual(result['provider_status'], 429)
                self.assertEqual(result['provider_code'], code)
                self.assertIn(expected, result['error'])
                self.assertNotIn('offline-openai-key', json.dumps(result))
        jobs = self.app.studio.state()['jobs']
        self.assertTrue(all(j['status'] == 'FAILED' and j['result']['provider_status'] == 429 for j in jobs))
        self.assertNotIn('offline-openai-key', json.dumps(jobs))
        self.assertEqual(len(self.gateway.requests), len(cases))
        self.assertEqual(list(self.app.studio.media_dir.iterdir()), [])

    def test_429_falls_back_to_safe_type_without_inventing_provider_code(self):
        self.add_openai()
        self.gateway.status, self.gateway.content_type = 429, 'application/json'
        for kind, expected in [('insufficient_quota', 'سهمیه'), ('rate_limit_error', 'بازهٔ زمانی')]:
            self.gateway.audio = json.dumps({'error': {'type': kind, 'code': 'offline-openai-key'}}).encode()
            status, result = self.generate()
            self.assertEqual(status, 429)
            self.assertIsNone(result['provider_code'])
            self.assertEqual(result['provider_type'], kind)
            self.assertIn(expected, result['error'])
            self.assertNotIn('offline-openai-key', json.dumps(result))

    def test_unrecognized_or_malformed_error_never_exposes_body_or_claims_cause(self):
        self.add_openai()
        self.gateway.status, self.gateway.content_type = 429, 'application/json'
        for body in [b'not JSON: offline-openai-key', b'null', b'[]',
                     b'{"error":"offline-openai-key"}',
                     b'{"error":{"code":["offline-openai-key"],"type":{}}}',
                     b'{"error":{"code":"offline-openai-key","message":"secret"}}',
                     b' ' * 65537 + b'{"error":{"code":"insufficient_quota"}}']:
            self.gateway.audio = body
            status, result = self.generate()
            self.assertEqual(status, 429)
            self.assertIsNone(result['provider_code'])
            self.assertIsNone(result['provider_type'])
            self.assertIn('علت دقیق', result['error'])
            self.assertNotIn('offline-openai-key', json.dumps(result))
            self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(len(self.gateway.requests), 7)

    def test_json_or_empty_payload_cannot_be_saved_as_successful_mp3(self):
        self.add_openai()
        for content_type, audio in [('application/json', b'{"error":"bad"}'),
                                    ('audio/mpeg', b''), ('audio/mpeg', b'{"error":"bad"}')]:
            self.gateway.content_type, self.gateway.audio = content_type, audio
            with self.assertRaises(RuntimeError):
                self.generate()
        self.assertEqual(list(self.app.studio.media_dir.iterdir()), [])
        self.assertTrue(all(j['status'] == 'FAILED' for j in self.app.studio.state()['jobs']))

    def test_concurrent_generation_is_rejected_without_second_call(self):
        self.add_openai()
        self.app.studio.voice_lock.acquire()
        try:
            self.assertEqual(self.generate()[0], 409)
        finally:
            self.app.studio.voice_lock.release()
        self.assertEqual(self.gateway.requests, [])


if __name__ == '__main__':
    unittest.main()
