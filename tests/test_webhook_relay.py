"""Exercise the public gateway against the real local agent; no Meta/AI traffic."""
import hashlib
import hmac
import http.client
import http.server
import importlib.util
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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('webhook_relay', ROOT / 'scripts/webhook_relay.py')
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)
spec = importlib.util.spec_from_file_location('tunnel_status', ROOT / 'scripts/webhook_tunnel_status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class WebhookRelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.backend_port = sock.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and not k.startswith(('IG_', 'AGENT_', 'META_'))}
        env.update(AGENT_DB_PATH=str(Path(cls.temp.name) / 'state.db'),
                   AGENT_WEBHOOK_HOST='127.0.0.1', AGENT_WEBHOOK_PORT=str(cls.backend_port),
                   IG_WEBHOOK_VERIFY_TOKEN='offline-verify', META_APP_SECRET='offline-secret')
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / 'instagram_ai_agent.py'), '--run-server'],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop_agent)
        for _ in range(80):
            try:
                conn = http.client.HTTPConnection('127.0.0.1', cls.backend_port, timeout=1)
                conn.request('GET', '/health')
                if conn.getresponse().status == 200:
                    break
            except OSError:
                time.sleep(0.1)
            finally:
                conn.close()
        else:
            raise RuntimeError('Agent did not start')
        cls.gateway = http.server.ThreadingHTTPServer(('127.0.0.1', 0), relay.make_handler(cls.backend_port))
        cls.worker = threading.Thread(target=cls.gateway.serve_forever, daemon=True)
        cls.worker.start()
        cls.addClassCleanup(cls.stop_gateway)

    @classmethod
    def stop_agent(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    @classmethod
    def stop_gateway(cls):
        cls.gateway.shutdown()
        cls.gateway.server_close()
        cls.worker.join(timeout=5)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.gateway.server_port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_dashboard_and_admin_are_blocked_even_with_localhost_host(self):
        for path in ['/', '/dashboard', '/api/status', '/api/add-key', '/health', '/.env',
                     '/assets/reference/aria-profile.jpg', '/media/anything', '/webhook/../api/status',
                     '/webhook;api/status', '/%77ebhook', '/webhook/',
                     'http://127.0.0.1:%d/api/status' % self.backend_port]:
            for method in ['GET', 'POST']:
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.request(method, path, b'', {'Host': 'localhost:8080'})[0], 404)

    def test_verification_and_raw_signed_event_round_trip(self):
        code, body = self.request('GET', '/webhook?hub.mode=subscribe&hub.verify_token=offline-verify&hub.challenge=12345')
        self.assertEqual((code, body), (200, b'12345'))
        self.assertEqual(self.request('GET', '/webhook?hub.mode=subscribe&hub.verify_token=wrong')[0], 403)
        payload = '{ "entry": [], "note": "سلام آریا" }'.encode('utf-8')
        signature = 'sha256=' + hmac.new(b'offline-secret', payload, hashlib.sha256).hexdigest()
        code, result = self.request('POST', '/webhook', payload, {'X-Hub-Signature-256': signature})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(result)['status'], 'EVENT_RECEIVED')
        self.assertEqual(self.request('POST', '/webhook', payload)[0], 403)
        self.assertEqual(self.request('POST', '/webhook', payload + b' ', {'X-Hub-Signature-256': signature})[0], 403)

    def test_framing_size_and_methods_are_restricted(self):
        for method in ['HEAD', 'OPTIONS', 'PUT', 'PATCH', 'DELETE', 'TRACE', 'CONNECT']:
            self.assertEqual(self.request(method, '/webhook')[0], 405)
        for headers, expected in [({'Content-Length': str(relay.MAX_BODY + 1)}, 413),
                                  ({'Content-Length': '-1'}, 400),
                                  ({'Content-Length': 'invalid'}, 400),
                                  ({'Content-Length': '0', 'Transfer-Encoding': 'chunked'}, 400)]:
            self.assertEqual(self.request('POST', '/webhook', b'', headers)[0], expected)
        self.assertEqual(self.request('GET', '/webhook', b'x')[0], 400)
        conn = http.client.HTTPConnection('127.0.0.1', self.gateway.server_port, timeout=3)
        try:
            conn.putrequest('POST', '/webhook')
            conn.putheader('Content-Length', '0')
            conn.putheader('Content-Length', '0')
            conn.endheaders()
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            conn.close()

    def test_status_probe_checks_the_real_gateway(self):
        status.check_routes('http://127.0.0.1:%d' % self.gateway.server_port)
        with self.assertRaises(RuntimeError):
            status.check_routes('http://127.0.0.1:%d' % self.backend_port)


class RelayUnavailableTests(unittest.TestCase):
    def test_unavailable_backend_returns_502(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            unused = sock.getsockname()[1]
            gateway = http.server.ThreadingHTTPServer(('127.0.0.1', 0), relay.make_handler(unused))
            worker = threading.Thread(target=gateway.serve_forever, daemon=True)
            worker.start()
            conn = http.client.HTTPConnection('127.0.0.1', gateway.server_port, timeout=3)
            try:
                conn.request('GET', '/webhook')
                response = conn.getresponse()
                self.assertEqual(response.status, 502)
                response.read()
            finally:
                conn.close()
                gateway.shutdown()
                gateway.server_close()
                worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
