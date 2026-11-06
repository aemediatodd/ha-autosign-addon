"""Per-thread HTTP budget; no retries of state-changing requests."""
import threading
import time
import requests

local = threading.local()

class Session(requests.Session):
    def request(self, method, url, **kwargs):
        remaining = getattr(local, 'deadline', time.monotonic() + 90) - time.monotonic()
        if remaining <= 0:
            raise requests.Timeout('Request budget exhausted')
        kwargs['timeout'] = (min(10, remaining), min(20, remaining))
        response = super().request(method, url, **kwargs)
        response.raise_for_status()
        return response

def get(url, **kwargs):
    with Session() as session:
        return session.get(url, **kwargs)

def post(url, **kwargs):
    with Session() as session:
        return session.post(url, **kwargs)
