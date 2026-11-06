"""Validated configuration, isolated execution, and secret-free persisted results."""
import copy
import logging
import re
import time
from urllib.parse import parse_qsl, unquote
from zoneinfo import ZoneInfo
from upstream.sign import gtfed, Miui, JiaoYiMao, TYYP, wyyyx, XiaoHeiHe
from upstream.push import Push
from http_client import local

PROVIDERS = {
    'MiUI': ('MIUI 历史版本', Miui, 'Sign', ('user', 'password')),
    'gtfed': ('好游快爆', gtfed, 'Sign', ('cookie',)),
    'JiaoYiMao': ('交易猫', JiaoYiMao, 'Sgin', ('cookie',)),
    'tyyp': ('天翼云盘', TYYP, 'Sgin', ('username', 'password')),
    'wyyyx': ('网易云游戏', wyyyx, 'Sgin', ('cookie',)),
    'XiaoHeiHe': ('小黑盒（未测试）', XiaoHeiHe, 'Sgin', ('cookie', 'imei')),
}
DEFAULT = {
    'schedule_enabled': False, 'run_time': '07:00', 'timezone': 'Asia/Hong_Kong',
    'accounts': {key: {'switch': False, **{field: '' for field in fields}}
                 for key, (_, _, _, fields) in PROVIDERS.items()},
    'push': {'PushMode': '', 'PushKey': {
        'Qmsg': '', 'Server': '',
        'Epwc': {'EnterpriseId': '', 'AppId': '', 'AppSecret': '', 'UserUid': ''},
        'Dingtalk': {'token': '', 'secret': '', 'atuser': '', 'atMobiles': '', 'isAtAll': False},
    }},
}

def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('配置字段不完整')
    if type(value['schedule_enabled']) is not bool:
        raise ValueError('定时开关必须为布尔值')
    if not isinstance(value['run_time'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value['run_time']):
        raise ValueError('时间须为 HH:MM')
    try:
        ZoneInfo(value['timezone'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('时区无效') from None
    def check_shape(actual, template):
        if isinstance(template, dict):
            if not isinstance(actual, dict) or set(actual) != set(template):
                raise ValueError('配置结构无效')
            for key in template:
                check_shape(actual[key], template[key])
        elif type(actual) is not type(template):
            raise ValueError('配置类型无效')
        elif isinstance(actual, str) and len(actual) > 16384:
            raise ValueError('配置字段过长')
    check_shape(value, DEFAULT)
    for key, account in value['accounts'].items():
        fields = PROVIDERS[key][3]
        if account['switch'] and any(not account[f].strip() for f in fields if f != 'imei'):
            raise ValueError(f'{PROVIDERS[key][0]}：请填写所需账户信息')
    if value['push']['PushMode'] not in ('', 'qmsg', 'server', 'epwc', 'dingtalk'):
        raise ValueError('未知推送方式')
    mode = value['push']['PushMode']
    keys = value['push']['PushKey']
    required = {'qmsg': [keys['Qmsg']], 'server': [keys['Server']],
                'epwc': [keys['Epwc'][field] for field in ('EnterpriseId', 'AppId', 'AppSecret', 'UserUid')],
                'dingtalk': [keys['Dingtalk']['token']]}
    if mode and any(not text.strip() for text in required[mode]):
        raise ValueError('请填写所选推送方式的必填信息')
    if mode == 'epwc' and not keys['Epwc']['AppId'].isdigit():
        raise ValueError('企业微信 AppId 须为数字')
    return copy.deepcopy(value)

def secrets(config):
    values = []
    def walk(node):
        if isinstance(node, dict):
            for val in node.values():
                walk(val)
        elif isinstance(node, str) and node:
            values.append(node)
    walk(config['accounts'])
    walk(config['push']['PushKey'])
    for account in config['accounts'].values():
        cookie = account.get('cookie', '')
        # Redact individual form/Cookie values as well as the complete captured string.
        for _, value in parse_qsl(cookie.replace(';', '&'), keep_blank_values=False):
            if value.strip():
                values.extend((value.strip(), unquote(value.strip())))
    return sorted(set(values), key=len, reverse=True)

def redact(message, config):
    message = str(message)
    for secret in secrets(config):
        message = message.replace(secret, '[redacted]')
    return re.sub(r'https?://\S+', '[URL]', message)[:1500]

def execute(config, selected=None):
    config = validate(config)
    results = []
    for key, (name, cls, method, _) in PROVIDERS.items():
        if selected and key != selected:
            continue
        if not config['accounts'][key]['switch']:
            continue
        local.deadline = time.monotonic() + 90
        try:
            message = getattr(cls(config['accounts']), method)()
            if not isinstance(message, str) or not message.strip():
                message = '平台未返回有效结果，请检查登录状态或接口变化'
            # Legacy handlers return their exception strings. Do not expose request details.
            if '错误' in message and ('错误信息' in message or '出现了错误' in message):
                message = '接口请求失败，请检查凭据、网络或上游接口变化'
            status = 'success' if ('签到成功' in message or '已经签到' in message or '签到过' in message or '进度已满' in message) else 'failed'
            if '请在 App' in message or '请先在 App' in message:
                status = 'action_required'
            results.append({'platform': key, 'name': name, 'status': status, 'message': redact(message, config)})
        except Exception as exc:
            results.append({'platform': key, 'name': name, 'status': 'failed',
                            'message': f'请求失败（{type(exc).__name__}），请检查登录状态、网络或接口变化'})
        logging.getLogger('autosign').info('Platform %s completed: %s', key, results[-1]['status'])
    push_status = 'disabled'
    if results and config['push']['PushMode']:
        local.deadline = time.monotonic() + 60
        try:
            Push('\n'.join(r['name'] + ': ' + r['message'] for r in results), config['push']).push()
            push_status = 'sent'
        except Exception as exc:
            push_status = 'failed:' + type(exc).__name__
    return {'results': results, 'push': push_status}
