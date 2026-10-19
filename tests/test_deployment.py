"""Offline deployment checks: real subprocess/HTTP/SQLite, no provider traffic."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

import instagram_ai_agent as agent

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_persistent_database_and_no_silent_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'nested' / 'state.db'
            db = agent.StateDatabase(str(path))
            db.upsert_api_key('custom', 'offline', 'test-placeholder', daily_token_limit=99)
            reopened = agent.StateDatabase(str(path))
            self.assertEqual(reopened.get_token_usage_report()['configured_keys'][0]['key_alias'], 'offline')
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            with self.assertRaises((OSError, sqlite3.Error)):
                agent.StateDatabase(str(Path(temp)))  # directory cannot be a DB

    def test_duplicate_source_is_in_sync(self):
        self.assertEqual((ROOT / 'instagram_ai_agent.py').read_bytes(), (ROOT / 'src/instagram_ai_agent.py').read_bytes())

    def test_explicit_verify_token_overrides_saved_token(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / 'state.db')
            db = agent.StateDatabase(path)
            db.save_instagram_account('offline-id', 'offline-token', webhook_verify_token='old-token')
            config = agent.AgentConfig(db_path=path, webhook_verify_token='rotated-token')
            orchestrator = agent.InstagramAgentOrchestrator(config)
            self.assertEqual(orchestrator.config.webhook_verify_token, 'rotated-token')

    def test_server_and_daemon_http_webhooks(self):
        for mode in ['--run-server', '--run-daemon']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and not k.startswith('IG_') and not k.startswith('AGENT_')}
                env.update(AGENT_DB_PATH=str(Path(temp) / 'state.db'), AGENT_WEBHOOK_HOST='127.0.0.1',
                           AGENT_WEBHOOK_PORT=str(port), IG_WEBHOOK_VERIFY_TOKEN='test-verify', META_APP_SECRET='test-secret')
                proc = subprocess.Popen([sys.executable, str(ROOT / 'instagram_ai_agent.py'), mode], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                base = f'http://127.0.0.1:{port}'
                try:
                    for _ in range(80):
                        if proc.poll() is not None:
                            self.fail(proc.stderr.read().decode())
                        try:
                            with urllib.request.urlopen(base + '/health', timeout=1) as response:
                                data = json.load(response)
                            break
                        except (OSError, urllib.error.URLError):
                            time.sleep(0.1)
                    else:
                        self.fail('HTTP startup timed out')
                    self.assertEqual(data['status'], 'ONLINE')
                    self.assertFalse(data['instagram_connected'])
                    self.assertEqual(data['token_report']['configured_keys'], [])
                    with urllib.request.urlopen(base + '/webhook?hub.mode=subscribe&hub.verify_token=test-verify&hub.challenge=123') as response:
                        self.assertEqual(response.read(), b'123')
                    body = b'{"entry": []}'
                    req = urllib.request.Request(base + '/webhook', data=body, method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as err:
                        urllib.request.urlopen(req)
                    self.assertEqual(err.exception.code, 403)
                    signature = 'sha256=' + hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()
                    req.add_header('X-Hub-Signature-256', signature)
                    with urllib.request.urlopen(req) as response:
                        self.assertEqual(json.load(response)['status'], 'EVENT_RECEIVED')
                    req = urllib.request.Request(base + '/api/add-key', data=b'[]', method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as err:
                        urllib.request.urlopen(req)
                    self.assertEqual(err.exception.code, 400)
                finally:
                    proc.terminate()
                    proc.wait(timeout=5)
                    proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
