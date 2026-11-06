"""Ingress-only UI, hot configuration, and persistent daily scheduling."""
import copy
import json
import logging
import os
from pathlib import Path
import secrets
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo
from engine import DEFAULT, PROVIDERS, execute, validate

DATA = Path(os.environ.get('AUTOSIGN_DATA', '/data'))
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
STOP = threading.Event()
CONFIG = copy.deepcopy(DEFAULT)
STATE = {'running': False, 'last_scheduled_date': None, 'last_run': None, 'results': [], 'push': 'disabled'}
LOG = logging.getLogger('autosign')

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)

def load():
    global CONFIG
    DATA.mkdir(parents=True, exist_ok=True)
    if (DATA / 'config.json').exists():
        CONFIG = validate(json.loads((DATA / 'config.json').read_text(encoding='utf-8')))
    if (DATA / 'state.json').exists():
        STATE.update(json.loads((DATA / 'state.json').read_text(encoding='utf-8')))
    STATE['running'] = False

def worker(config, selected):
    try:
        result = execute(config, selected)
        with LOCK:
            STATE.update(result)
            STATE['last_run'] = datetime.now(ZoneInfo(config['timezone'])).isoformat()
    except Exception as exc:
        LOG.error('Execution failed: %s', type(exc).__name__)
        with LOCK:
            STATE['results'] = [{'name': '任务', 'status': 'failed', 'message': '执行失败，请检查配置'}]
    finally:
        with LOCK:
            STATE['running'] = False
            write_json(DATA / 'state.json', STATE)

def start_run(selected=None, scheduled_date=None):
    with LOCK:
        if STATE['running']:
            return False
        snapshot = copy.deepcopy(CONFIG)
        STATE['running'] = True
        if scheduled_date:
            STATE['last_scheduled_date'] = scheduled_date
        write_json(DATA / 'state.json', STATE)
        threading.Thread(target=worker, args=(snapshot, selected), daemon=True).start()
        return True

def schedule_tick(now=None):
    with LOCK:
        now = now or datetime.now(ZoneInfo(CONFIG['timezone']))
        today = now.date().isoformat()
        if (CONFIG['schedule_enabled'] and any(a['switch'] for a in CONFIG['accounts'].values())
                and now.strftime('%H:%M') >= CONFIG['run_time']
                and STATE['last_scheduled_date'] != today and not STATE['running']):
            start_run(scheduled_date=today)

def scheduler():
    while not STOP.wait(15):
        try:
            schedule_tick()
        except Exception as exc:
            LOG.error('Scheduler failure: %s', type(exc).__name__)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def allowed(self):
        # Supervisor ingress is the authentication boundary. No published host ports.
        return self.client_address[0] in ('172.30.32.2', '127.0.0.1', '::1')

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        payload = body.encode('utf-8') if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.allowed():
            return self.send(403, {'error': 'Ingress access required'})
        path = self.path.split('?', 1)[0].rstrip('/')
        if path in ('', '/index.html'):
            page = Path(__file__).with_name('index.html').read_text(encoding='utf-8')
            return self.send(200, page.replace('__CSRF_TOKEN__', TOKEN), 'text/html; charset=utf-8')
        if self.headers.get('X-AutoSign-Token') != TOKEN:
            return self.send(403, {'error': 'Invalid session'})
        with LOCK:
            if path == '/api/config':
                return self.send(200, CONFIG)
            if path == '/api/status':
                return self.send(200, STATE)
        self.send(404, {'error': 'Not found'})

    def do_POST(self):
        global CONFIG
        if not self.allowed() or self.headers.get('X-AutoSign-Token') != TOKEN:
            return self.send(403, {'error': 'Invalid session'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send(415, {'error': 'JSON required'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 262144:
                return self.send(413, {'error': 'Invalid request size'})
            value = json.loads(self.rfile.read(size))
            path = self.path.rstrip('/')
            if path == '/api/config':
                config = validate(value)
                with LOCK:
                    if STATE['running']:
                        return self.send(409, {'error': '任务正在运行，请完成后再保存'})
                    write_json(DATA / 'config.json', config)
                    CONFIG = config
                return self.send(200, {'ok': True})
            if path == '/api/run':
                selected = value.get('platform')
                if selected is not None and selected not in PROVIDERS:
                    raise ValueError('未知平台')
                return self.send(202 if start_run(selected) else 409, {'ok': True})
            return self.send(404, {'error': 'Not found'})
        except (ValueError, TypeError, AttributeError):
            self.send(400, {'error': '配置或请求无效，请检查时间、时区和已启用平台的凭据'})
        except OSError:
            self.send(500, {'error': '保存失败，请检查磁盘空间'})

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    load()
    threading.Thread(target=scheduler, daemon=True).start()
    LOG.info('AutoSign 0.1.1 listening on ingress port 8099; XiaoHeiHe untested')
    ThreadingHTTPServer(('0.0.0.0', 8099), Handler).serve_forever()

if __name__ == '__main__':
    main()
