from dataclasses import dataclass

@dataclass
class Response:
    headers: dict
    body: dict
    response_code: int


@dataclass
class Request:
    url: str
    headers: dict
    response: list[Response]

@dataclass
class Session:
    """Mainly the cookies, storage, etc"""
    pass

@dataclass
class Result:
    request: list[Request]

class Playwright:
    def __init__(self):
        pass

    def __aenter__(self):
        pass

    def __aexit__(self, exc_type, exc, tb):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def get_browser(self):
        pass

    def crawl(self, url):
        pass

    def wait(self):
        pass

    def screenshot(self):
        pass

    def execute(self, actions):
        pass