"""Regression checks for durable daily jobs, resources and draft preservation."""
import base64
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from PIL import Image, features
import instagram_ai_agent as agent
from aria_studio import read_profile


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {v['env_key']:'' for v in agent.PROVIDER_DEFAULTS.values()})
        self.env.start()
        self.config = agent.AgentConfig(db_path=str(Path(self.temp.name)/'state.db'), ig_access_token='', ig_user_id='')
        self.app = agent.InstagramAgentOrchestrator(self.config)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_daily_pack_once_after_0900_survives_restart_without_instagram(self):
        self.app.db.upsert_api_key('custom','offline','fake-key')
        now = dt.datetime(2026,10,20,8,59,tzinfo=ZoneInfo('Asia/Tehran'))
        with patch.object(self.app.brain,'generate_daily_content_pack',return_value={'topic':'امروز','scheduled_stories':[]}) as generate:
            self.assertFalse(self.app.studio.daily_tick(now))
            self.assertTrue(self.app.studio.daily_tick(now.replace(hour=9,minute=0)))
            self.assertFalse(self.app.studio.daily_tick(now.replace(hour=10)))
            self.assertEqual(generate.call_count,1)
        restarted = agent.InstagramAgentOrchestrator(self.config)
        self.assertFalse(restarted.studio.daily_tick(now.replace(hour=12)))
        state = restarted.studio.state()
        self.assertEqual(len(state['packs']),1)
        self.assertEqual(state['jobs'][0]['status'],'DONE')
        restarted.studio.handle_post('/api/studio-settings',{'enabled':False})
        self.assertFalse(restarted.studio.daily_tick(now.replace(day=21,hour=10)))

    def test_failed_daily_job_is_recorded_without_repeated_api_charges(self):
        self.app.db.upsert_api_key('custom','offline','fake-key')
        now=dt.datetime(2026,10,20,10,tzinfo=ZoneInfo('Asia/Tehran'))
        with patch.object(self.app.brain,'generate_daily_content_pack',side_effect=RuntimeError('offline')):
            self.assertTrue(self.app.studio.daily_tick(now))
        self.assertFalse(self.app.studio.daily_tick(now))
        self.assertEqual(self.app.studio.state()['jobs'][0]['result']['error'],'offline')

    def test_png_draft_and_key_pause_persist(self):
        self.app.db.upsert_api_key('custom','offline','secret')
        image=io.BytesIO();Image.new('RGB',(1080,1920),'navy').save(image,format='PNG')
        _,response=self.app.studio.handle_post('/api/save-draft',{'headline':'سلام ایران (AI)','image':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()})
        self.app.studio.handle_post('/api/toggle-key',{'alias':'offline','active':False})
        restarted=agent.InstagramAgentOrchestrator(self.config)
        self.assertEqual(restarted.studio.state()['drafts'][0]['headline'],'سلام ایران (AI)')
        self.assertTrue((restarted.studio.media_dir/(response['draft']['id']+'.png')).is_file())
        self.assertFalse(restarted.db.get_token_usage_report()['configured_keys'][0]['is_active'])
        self.assertFalse(restarted.studio.state()['media_capabilities']['image_configured'])

    def test_env_key_pause_and_budget_survive_restart(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-secret'}):
            self.app.db.sync_env_keys_to_vault()
            self.app.db.upsert_api_key('openai','openai_env','offline-secret',daily_token_limit=1234)
            self.app.studio.handle_post('/api/toggle-key',{'alias':'openai_env','active':False})
            self.app.db.sync_env_keys_to_vault()
        row=self.app.db.get_token_usage_report()['configured_keys'][0]
        self.assertFalse(row['is_active']);self.assertEqual(row['daily_token_limit'],1234)

    def test_persian_font_and_original_character_are_loaded(self):
        profile=read_profile()
        self.assertEqual(agent.PERSONA_SYSTEM_PROMPT,profile['system_prompt'])
        self.assertTrue(features.check('raqm'))
        font=agent.StoryMediaGenerator._get_persian_rtl_font(32)
        self.assertIn('assets/fonts/Vazirmatn',str(font.path))
        for path in profile['assets'].values():
            with Image.open(agent.PROJECT_ROOT/path.lstrip('/')) as image:self.assertGreater(image.width,700)
        with patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError,'OpenAI'):
                self.app.studio.generate_image('تهران')
            network.assert_not_called()

if __name__=='__main__':unittest.main()

class ImageGatewayTests(unittest.TestCase):
    def test_image_api_uses_openai_key_saves_vertical_file_and_logs_usage(self):
        import http.server
        import threading
        class Gateway(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.received=(self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                output=io.BytesIO();Image.new('RGB',(128,192),'navy').save(output,format='PNG')
                body=json.dumps({'data':[{'b64_json':base64.b64encode(output.getvalue()).decode()}],'usage':{'input_tokens':7,'output_tokens':11}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{v['env_key']:'' for v in agent.PROVIDER_DEFAULTS.values()}):
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Gateway)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                app=agent.InstagramAgentOrchestrator(agent.AgentConfig(db_path=str(Path(temp)/'state.db'),ig_user_id='',ig_access_token=''))
                app.db.upsert_api_key('custom','wrong_provider','wrong-key',priority=1)
                app.db.upsert_api_key('openai','image','offline-key',base_url='http://127.0.0.1:'+str(server.server_port),priority=20)
                url=app.studio.generate_image('تهران')
                self.assertEqual(server.received[0],'/images/generations')
                self.assertEqual(server.received[1],'Bearer offline-key')
                self.assertIn(read_profile()['visual_seed_prompt_en'],server.received[2]['prompt'])
                with Image.open(app.studio.media_dir/url.split('/')[-1]) as image:self.assertEqual(image.size,(1080,1920))
                rows=app.db.get_token_usage_report()['configured_keys']
                self.assertEqual(next(r for r in rows if r['key_alias']=='image')['used_tokens_today'],18)
                self.assertEqual(app.studio.state()['jobs'][0]['result']['media_type'],'image')
            finally:server.shutdown();server.server_close()
