import copy
import json
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer
from zoneinfo import ZoneInfo
from unittest.mock import Mock
import pytest
import requests
import server

@pytest.fixture(autouse=True)
def reset(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    monkeypatch.setattr(server, 'CONFIG', copy.deepcopy(server.DEFAULT))
    monkeypatch.setattr(server, 'STATE', {'running': False, 'last_scheduled_date': None, 'results': []})

def test_schedule_runs_once_per_day_and_persists_claim(monkeypatch):
    server.CONFIG['schedule_enabled'] = True
    server.CONFIG['accounts']['MiUI']['switch'] = True
    server.CONFIG['accounts']['MiUI'].update(user='test', password='test')
    thread = Mock()
    monkeypatch.setattr(server.threading, 'Thread', thread)
    server.schedule_tick(datetime(2026, 11, 6, 8, tzinfo=ZoneInfo('Asia/Hong_Kong')))
    assert thread.call_count == 1
    server.STATE['running'] = False
    server.schedule_tick(datetime(2026, 11, 6, 9, tzinfo=ZoneInfo('Asia/Hong_Kong')))
    assert thread.call_count == 1
    persisted = json.loads((server.DATA / 'state.json').read_text())
    assert persisted['last_scheduled_date'] == '2026-11-06'

def test_manual_runs_do_not_overlap(monkeypatch):
    monkeypatch.setattr(server.threading, 'Thread', Mock())
    assert server.start_run()
    assert not server.start_run()

def test_ingress_rejects_direct_peer():
    handler = object.__new__(server.Handler)
    handler.client_address = ('192.168.30.55', 1234)
    assert not handler.allowed()

def test_api_requires_token_and_hot_saves_config():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{httpd.server_port}'
    try:
        assert requests.get(url + '/api/config', timeout=5).status_code == 403
        headers = {'X-AutoSign-Token': server.TOKEN}
        config = copy.deepcopy(server.DEFAULT)
        config['run_time'] = '08:30'
        assert requests.post(url + '/api/config', json=config, headers=headers, timeout=5).status_code == 200
        assert server.CONFIG['run_time'] == '08:30'
        assert (server.DATA / 'config.json').exists()
        assert requests.post(url + '/api/run', json={'platform': 'invalid'}, headers=headers, timeout=5).status_code == 400
        r = requests.get(url + '/', timeout=5)
        assert r.status_code == 200 and server.TOKEN in r.text
        assert 'no-store' in r.headers['Cache-Control']
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)
