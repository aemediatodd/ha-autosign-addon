import copy
from unittest.mock import Mock
import pytest
import requests
import engine
import http_client
from upstream.sign import Miui

def test_defaults_make_no_network_requests(monkeypatch):
    monkeypatch.setattr(requests.Session, 'request', Mock(side_effect=AssertionError('Unexpected network')))
    assert engine.execute(copy.deepcopy(engine.DEFAULT)) == {'results': [], 'push': 'disabled'}

def test_config_requires_enabled_credentials_and_valid_schedule():
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI']['switch'] = True
    with pytest.raises(ValueError):
        engine.validate(config)
    config = copy.deepcopy(engine.DEFAULT)
    config['run_time'] = '24:00'
    with pytest.raises(ValueError):
        engine.validate(config)
    config = copy.deepcopy(engine.DEFAULT)
    config['timezone'] = '../etc/passwd'
    with pytest.raises(ValueError):
        engine.validate(config)

def test_missing_push_config_cannot_report_sent():
    config = copy.deepcopy(engine.DEFAULT)
    config['push']['PushMode'] = 'dingtalk'
    with pytest.raises(ValueError):
        engine.validate(config)

def test_miui_login_returns_actual_cookies(monkeypatch):
    response = Mock(text='1', cookies={'session': 'test-cookie'})
    monkeypatch.setattr(http_client, 'post', Mock(return_value=response))
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI'].update(user='example', password='test-password')
    assert Miui(config['accounts']).Login() == response.cookies

def test_platform_error_is_isolated_and_secret_is_redacted(monkeypatch):
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI'].update(switch=True, user='example', password='secret-password')
    config['accounts']['gtfed'].update(switch=True, cookie='token=fake-secret')
    broken = Mock(return_value=Mock(Sign=Mock(side_effect=requests.Timeout('secret-password'))))
    good = Mock(return_value=Mock(Sign=Mock(return_value='签到成功 token=fake-secret')))
    monkeypatch.setitem(engine.PROVIDERS, 'MiUI', ('MIUI', broken, 'Sign', ('user', 'password')))
    monkeypatch.setitem(engine.PROVIDERS, 'gtfed', ('好游快爆', good, 'Sign', ('cookie',)))
    result = engine.execute(config)
    assert [r['status'] for r in result['results']] == ['failed', 'success']
    assert 'secret-password' not in str(result)
    assert 'fake-secret' not in str(result)

def test_http_has_timeout_and_rejects_http_error(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError('503')
    request = Mock(return_value=response)
    monkeypatch.setattr(requests.Session, 'request', request)
    with pytest.raises(requests.HTTPError):
        http_client.get('https://example.invalid')
    timeout = request.call_args.kwargs['timeout']
    assert 0 < timeout[0] <= 10 and 0 < timeout[1] <= 20

def test_http_budget_prevents_further_requests(monkeypatch):
    monkeypatch.setattr(http_client.local, 'deadline', 0, raising=False)
    with pytest.raises(requests.Timeout):
        http_client.get('https://example.invalid')

def test_push_rejection_is_not_reported_as_sent(monkeypatch):
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['gtfed'].update(switch=True, cookie='fake-cookie')
    config['push']['PushMode'] = 'dingtalk'
    config['push']['PushKey']['Dingtalk']['token'] = 'fake-token'
    fake = Mock(return_value=Mock(Sign=Mock(return_value='签到成功')))
    monkeypatch.setitem(engine.PROVIDERS, 'gtfed', ('好游快爆', fake, 'Sign', ('cookie',)))
    monkeypatch.setattr(http_client, 'post', Mock(return_value=Mock(json=Mock(return_value={'errcode': 310000}))))
    assert engine.execute(config)['push'].startswith('failed:')
