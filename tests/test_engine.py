import copy
from unittest.mock import Mock
import pytest
import requests
import rsa
import engine
import http_client
from upstream.sign import Miui, TYYP, gtfed

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

def test_cloud189_current_login_encrypts_credentials():
    public, private = rsa.newkeys(512)
    key = public.save_pkcs1('PEM')
    # The server supplies an OpenSSL SubjectPublicKeyInfo public key.
    import base64
    import pyasn1.codec.der.encoder
    import pyasn1.type.univ
    import pyasn1.codec.der.decoder
    pubseq, _ = pyasn1.codec.der.decoder.decode(public.save_pkcs1('DER'))
    algorithm = pyasn1.type.univ.Sequence()
    algorithm.setComponentByPosition(0, pyasn1.type.univ.ObjectIdentifier('1.2.840.113549.1.1.1'))
    algorithm.setComponentByPosition(1, pyasn1.type.univ.Null(''))
    subject = pyasn1.type.univ.Sequence()
    subject.setComponentByPosition(0, algorithm)
    subject.setComponentByPosition(1, pyasn1.type.univ.BitString.fromOctetString(pyasn1.codec.der.encoder.encode(pubseq)))
    pem_body = base64.b64encode(pyasn1.codec.der.encoder.encode(subject)).decode()
    session = Mock()
    session.get.side_effect = [Mock(url='https://open.e.189.cn/login?appId=cloud&lt=test-lt&reqId=test-id'), Mock()]
    conf = {'appKey': 'cloud', 'returnUrl': 'https://cloud.189.cn/callback', 'paramId': 'test-param'}
    session.post.side_effect = [
        Mock(json=lambda: {'result': 0, 'data': conf}),
        Mock(json=lambda: {'result': 0, 'data': {'pubKey': pem_body, 'pre': '{RSA}'}}),
        Mock(json=lambda: {'result': 0, 'toUrl': 'https://cloud.189.cn/callback'}),
    ]
    account = copy.deepcopy(engine.DEFAULT)['accounts']
    result = TYYP(account).Login(session, 'test-user', 'test-password')
    assert result is session
    payload = session.post.call_args.kwargs['data']
    assert rsa.decrypt(base64.b64decode(payload['userName'][5:]), private) == b'test-user'
    assert rsa.decrypt(base64.b64decode(payload['epd'][5:]), private) == b'test-password'
    assert payload['returnUrl'] == 'https%3A%2F%2Fcloud.189.cn%2Fcallback'
    assert 'password' not in payload

def test_cloud189_rejects_stale_login_page_before_sending_password():
    session = Mock()
    session.get.return_value.url = 'https://open.e.189.cn/unexpected'
    account = copy.deepcopy(engine.DEFAULT)['accounts']
    assert TYYP(account).Login(session, 'test-user', 'test-password') is None
    session.post.assert_not_called()

def test_cloud189_lottery_failure_preserves_success(monkeypatch):
    from unittest.mock import MagicMock
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.side_effect = [Mock(json=lambda: {'netdiskBonus': 50, 'isSign': False}), requests.Timeout(), requests.Timeout()]
    monkeypatch.setattr(http_client, 'Session', Mock(return_value=session))
    monkeypatch.setattr(TYYP, 'Login', Mock(return_value=session))
    account = copy.deepcopy(engine.DEFAULT)['accounts']
    account['tyyp'].update(username='test', password='test')
    message = TYYP(account).Sgin()
    assert '签到成功' in message
    assert message.count('抽奖请求失败') == 2

def test_3839_current_endpoint_accepts_new_success_code(monkeypatch):
    post = Mock(return_value=Mock(json=lambda: {'key': '1001'}))
    monkeypatch.setattr(http_client, 'post', post)
    account = copy.deepcopy(engine.DEFAULT)['accounts']
    account['gtfed']['cookie'] = 'ac=Sign&token=test'
    assert '签到成功' in gtfed(account).Sign()
    assert '/cornfarm/ajax_sign.php' in post.call_args.kwargs['url']

def test_redacts_individual_cookie_and_form_values():
    config = copy.deepcopy(engine.DEFAULT)
    config['accounts']['gtfed']['cookie'] = 'token=secret-one&other=secret-two'
    config['accounts']['JiaoYiMao']['cookie'] = 'sid=secret-three; _csrfToken=secret-four'
    message = engine.redact('secret-one secret-two secret-three secret-four', config)
    assert 'secret-' not in message
