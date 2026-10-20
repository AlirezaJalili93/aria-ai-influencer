"""Public HTTPS frontend: real Caddy + real backend, with a test-only local CA."""
import base64
import hashlib
import hmac
import http.client
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


frontend = module('public_dashboard', 'scripts/public_dashboard.py')
relay = module('relay', 'scripts/webhook_relay.py')
HASH = '$2a$14$eWRV18875Ea.qblxP/k7n.Uq2MYRfQj4lwiw4FNXoB091tuloLJWG'


class PublicConfigTests(unittest.TestCase):
    def test_public_config_explicitly_uses_ip_acme_profile_and_password(self):
        text = frontend.render_config('195.248.241.48', 'aria', HASH)
        self.assertIn('profile shortlived', text)
        self.assertIn('basic_auth', text)
        self.assertIn('header_up -Authorization', text)
        self.assertIn('not header Origin https://195.248.241.48', text)
        self.assertIn('reverse_proxy 127.0.0.1:8081', text)
        self.assertNotIn('tls internal', text)
        self.assertIn('admin off', text)

    def test_configuration_values_cannot_inject_public_routes(self):
        for values in [('195.248.241.48', 'aria\nrespond 200', HASH, 8080),
                       ('195.248.241.48', 'aria', 'plain-password', 8080),
                       ('195.248.241.48', 'aria', HASH, 443),
                       ('bad-address', 'aria', HASH, 8080)]:
            with self.assertRaises(ValueError):
                frontend.render_config(*values)


@unittest.skipUnless(os.getenv('ARIA_TEST_CADDY'), 'Set ARIA_TEST_CADDY to a verified Caddy binary for HTTPS integration')
class PublicHTTPSIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        ports = []
        for _ in range(2):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                ports.append(sock.getsockname()[1])
        cls.backend_port, cls.https_port = ports
        env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and not k.startswith(('IG_', 'AGENT_', 'META_'))}
        env.update(AGENT_DB_PATH=str(cls.directory / 'state.db'), AGENT_WEBHOOK_HOST='127.0.0.1',
                   AGENT_WEBHOOK_PORT=str(cls.backend_port), META_APP_SECRET='offline-public-secret',
                   IG_WEBHOOK_VERIFY_TOKEN='offline-verify')
        cls.log = open(cls.directory / 'runtime.log', 'w+')
        cls.addClassCleanup(cls.log.close)
        cls.agent = subprocess.Popen([sys.executable, str(ROOT / 'instagram_ai_agent.py'), '--run-server'],
                                     env=env, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop, cls.agent)
        for _ in range(100):
            conn = http.client.HTTPConnection('127.0.0.1', cls.backend_port, timeout=1)
            try:
                conn.request('GET', '/health')
                if conn.getresponse().status == 200:
                    break
            except OSError:
                time.sleep(.1)
            finally:
                conn.close()
        else:
            raise RuntimeError('Agent did not start')
        cls.gateway = http.server.ThreadingHTTPServer(('127.0.0.1', 0), relay.make_handler(cls.backend_port))
        threading.Thread(target=cls.gateway.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.gateway.server_close)
        cls.addClassCleanup(cls.gateway.shutdown)
        config = frontend.render_config('127.0.0.1', 'aria', HASH, cls.backend_port, cls.https_port)
        config = config.replace('admin off', 'admin off\n    auto_https disable_redirects\n    skip_install_trust')
        config = config.replace('127.0.0.1:8081', '127.0.0.1:' + str(cls.gateway.server_port))
        config = re.sub(r'tls \{.*?\n    \}', 'tls internal', config, count=1, flags=re.S)
        path = cls.directory / 'Caddyfile'
        path.write_text(config, encoding='utf-8')
        env.update(XDG_DATA_HOME=str(cls.directory / 'data'), XDG_CONFIG_HOME=str(cls.directory / 'config'))
        cls.caddy = subprocess.Popen([os.environ['ARIA_TEST_CADDY'], 'run', '--config', str(path), '--adapter', 'caddyfile'],
                                     env=env, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop, cls.caddy)
        root_cert = cls.directory / 'data/caddy/pki/authorities/local/root.crt'
        for _ in range(150):
            if root_cert.exists():
                cls.context = ssl.create_default_context(cafile=str(root_cert))
                try:
                    if cls.request('GET', '/dashboard')[0] == 401:
                        break
                except OSError:
                    pass
            if cls.caddy.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError(cls.log.read())
            time.sleep(.1)
        else:
            cls.log.seek(0)
            raise RuntimeError(cls.log.read())
        cls.origin = 'https://127.0.0.1:' + str(cls.https_port)

    @classmethod
    def stop(cls, process):
        process.terminate()
        process.wait(timeout=5)

    @classmethod
    def request(cls, method, path, body=None, authenticated=False, headers=None):
        extra = dict(headers or {})
        if authenticated:
            extra['Authorization'] = 'Basic ' + base64.b64encode(b'aria:Local-test-password-2026').decode()
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
            extra['Content-Type'] = 'application/json'
        conn = http.client.HTTPSConnection('127.0.0.1', cls.https_port, context=cls.context, timeout=10)
        try:
            conn.request(method, path, body=body, headers=extra)
            result = conn.getresponse()
            return result.status, dict(result.getheaders()), result.read()
        finally:
            conn.close()

    def test_anonymous_cannot_read_dashboard_keys_assets_or_media(self):
        for path in ['/', '/dashboard', '/api/status', '/api/studio', '/dashboard.js', '/media/secret.mp3',
                     '/assets/reference/aria-profile.jpg', '/.env', '/webhook/../api/status', '/webhook/']:
            with self.subTest(path=path):
                code, headers, _ = self.request('GET', path)
                self.assertEqual(code, 401)
                self.assertIn('www-authenticate', {k.lower(): v for k, v in headers.items()})

    def test_authenticated_browser_can_read_page_assets_and_change_settings(self):
        code, _, page = self.request('GET', '/dashboard', authenticated=True)
        self.assertEqual(code, 200)
        self.assertIn('داشبورد مدیریت'.encode(), page)
        self.assertEqual(self.request('GET', '/assets/fonts/Vazirmatn-Regular.ttf', authenticated=True)[0], 200)
        code, _, body = self.request('POST', '/api/studio-settings', {'enabled': False}, True, {'Origin': self.origin})
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)['settings']['enabled'])
        self.assertEqual(self.request('GET', '/api/status', authenticated=True)[0], 200)

    def test_cross_origin_requests_are_denied_even_with_valid_password(self):
        for headers in [{'Origin': 'https://attacker.invalid'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(self.request('POST', '/api/studio-settings', {'enabled': True}, True, headers)[0], 403)
        wrong = 'Basic ' + base64.b64encode(b'aria:wrong-password').decode()
        self.assertEqual(self.request('GET', '/api/status', headers={'Authorization': wrong})[0], 401)

    def test_external_link_navigation_reaches_login_and_keeps_password_required(self):
        navigation = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
        self.assertEqual(self.request('GET', '/dashboard', headers=navigation)[0], 401)
        self.assertEqual(self.request('GET', '/dashboard', authenticated=True, headers=navigation)[0], 200)
        # CORS/fetch reads, frames and cross-site writes must not inherit this exception.
        for method, headers in [('GET', {**navigation, 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'}),
                                ('GET', {**navigation, 'Sec-Fetch-Dest': 'iframe'}),
                                ('POST', navigation)]:
            with self.subTest(method=method, headers=headers):
                self.assertEqual(self.request(method, '/api/status', authenticated=True, headers=headers)[0], 403)

    def test_public_webhook_verification_and_signature_remain_independent(self):
        self.assertEqual(self.request('GET', '/webhook')[0], 403)
        code, _, body = self.request('GET', '/webhook?hub.mode=subscribe&hub.verify_token=offline-verify&hub.challenge=777')
        self.assertEqual((code, body), (200, b'777'))
        payload = b'{"entry":[]}'
        self.assertEqual(self.request('POST', '/webhook', payload)[0], 403)
        signature = 'sha256=' + hmac.new(b'offline-public-secret', payload, hashlib.sha256).hexdigest()
        self.assertEqual(self.request('POST', '/webhook', payload, headers={'X-Hub-Signature-256': signature})[0], 200)


if __name__ == '__main__':
    unittest.main()
