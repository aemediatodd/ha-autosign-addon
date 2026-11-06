"""Deliver results to Home Assistant's built-in persistent notification service."""
import os
from http_client import Session


def send_notification(results):
    token = os.environ.get('SUPERVISOR_TOKEN')
    if not token:
        raise RuntimeError('Home Assistant API token unavailable')
    payload = {
        'title': 'AutoSign 自动签到',
        'message': '\n\n'.join(item['name'] + '：' + item['message'] for item in results),
        'notification_id': 'autosign_results',
    }
    with Session() as session:
        session.trust_env = False
        response = session.post(
            'http://supervisor/core/api/services/persistent_notification/create',
            headers={'Authorization': 'Bearer ' + token},
            json=payload,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError('Home Assistant notification was not accepted')
