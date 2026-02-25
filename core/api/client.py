import requests


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get(self, endpoint: str, **kwargs):
        return requests.get(f"{self.base_url}{endpoint}", **kwargs)