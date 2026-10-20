import os
import requests
import pybreaker

class HttpClient:
    def __init__(self):
        pass

    def call(self, url: str, method: str = 'GET', json: dict = None, timeout: int = 2, fail_max: int = 3, reset_timeout: int = 30):
        cb = pybreaker.CircuitBreaker(fail_max=fail_max, reset_timeout=reset_timeout, name=url)
        @cb
        def _do():
            r = requests.request(method, url, json=json, timeout=timeout)
            if r.status_code >= 500:
                raise Exception(f"HTTP {r.status_code}")
            return r
        return _do()
