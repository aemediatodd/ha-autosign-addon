import copy
import json
from unittest.mock import MagicMock, Mock
import pytest
import engine
import notifications
import server


def test_uses_ha_service_with_token_and_without_environment_proxy(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    session.post.return_value.status_code = 200
    monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-supervisor-token')
    monkeypatch.setattr(notifications, 'Session', Mock(return_value=session))
    notifications.send_notification([{'name': 'MIUI', 'message': '签到成功'}])
    args = session.post.call_args
    assert args.args[0] == 'http://supervisor/core/api/services/persistent_notification/create'
    assert args.kwargs['headers']['Authorization'] == 'Bearer test-supervisor-token'
    assert args.kwargs['json'] == {
        'title': 'AutoSign 自动签到', 'message': 'MIUI：签到成功', 'notification_id': 'autosign_results',
    }
    assert session.trust_env is False
    assert args.kwargs['allow_redirects'] is False


def test_missing_token_cannot_report_notification_success(monkeypatch):
    monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
    with pytest.raises(RuntimeError):
        notifications.send_notification([{'name': 'MIUI', 'message': '签到成功'}])


def test_ha_rejection_cannot_report_notification_success(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    session.post.return_value.status_code = 403
    monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
    monkeypatch.setattr(notifications, 'Session', Mock(return_value=session))
    with pytest.raises(RuntimeError):
        notifications.send_notification([{'name': 'MIUI', 'message': '签到成功'}])


def test_old_push_config_migration_preserves_accounts_and_schedule(tmp_path, monkeypatch):
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI'].update(switch=True, user='test-user', password='test-password')
    config['run_time'] = '08:30'
    config['push'] = {'PushMode': 'dingtalk', 'PushKey': {'token': 'old-token'}}
    (tmp_path / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setattr(server, 'DATA', tmp_path)
    monkeypatch.setattr(server, 'CONFIG', copy.deepcopy(engine.DEFAULT))
    server.load()
    persisted = json.loads((tmp_path / 'config.json').read_text(encoding='utf-8'))
    assert persisted['accounts'] == config['accounts']
    assert persisted['run_time'] == '08:30'
    assert persisted['push'] == {'enabled': True}
    assert 'old-token' not in json.dumps(persisted)


def test_disabled_notifications_make_no_ha_call(monkeypatch):
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI'].update(switch=True, user='test-user', password='test-password')
    config['push']['enabled'] = False
    fake = Mock(return_value=Mock(Sign=Mock(return_value='签到成功')))
    monkeypatch.setitem(engine.PROVIDERS, 'MiUI', ('MIUI', fake, 'Sign', ('user', 'password')))
    send = Mock(side_effect=AssertionError('Unexpected notification'))
    monkeypatch.setattr(engine, 'send_notification', send)
    assert engine.execute(config)['push'] == 'disabled'
    send.assert_not_called()


def test_notification_receives_redacted_platform_result(monkeypatch):
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['MiUI'].update(switch=True, user='test-user', password='test-password')
    fake = Mock(return_value=Mock(Sign=Mock(return_value='签到成功 test-password')))
    monkeypatch.setitem(engine.PROVIDERS, 'MiUI', ('MIUI', fake, 'Sign', ('user', 'password')))
    send = Mock()
    monkeypatch.setattr(engine, 'send_notification', send)
    assert engine.execute(config)['push'] == 'sent'
    assert 'test-password' not in str(send.call_args)
