import logging
import random
import urllib3
from requests.cookies import cookiejar_from_dict, merge_cookies
from espider.utils.tools import *
from espider.settings import USER_AGENT_LIST, __REQUEST_KEYS__
from espider.network.request import RequestThread

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class BaseSpider(object):
    def __init__(
            self,
            url=None,
            method=None,
            data=None,
            json=None,
            headers=None,
            cookies=None,
            **kwargs
    ):
        self.method = method
        if not self.method: self.method = 'POST' if data or json else 'GET'

        self.spider = {
            'url': url_to_dict(url),
            'data': body_to_dict(data),
            'json': json_to_dict(json),
            'headers': {**self._init_header(), **headers_to_dict(headers)},
            'cookies': cookiejar_from_dict(cookies_to_dict(cookies)),
        }

        self.request_kwargs = {}
        for key, value in kwargs.items():
            if key in __REQUEST_KEYS__ and key not in self.spider.keys():
                self.request_kwargs[key] = value

    def _init_header(self):
        if self.method == 'POST':
            content_type = 'application/x-www-form-urlencoded; charset=UTF-8'
            if self.spider.get('json'): content_type = 'application/json; charset=UTF-8'
            return {'User-Agent': random.choice(USER_AGENT_LIST), 'Content-Type': content_type}
        else:
            return {'User-Agent': random.choice(USER_AGENT_LIST)}

    @property
    def url(self):
        protocol = self.spider['url'].get('protocol')
        domain = self.spider['url'].get('domain')
        path = '/'.join(self.spider['url'].get('path'))
        _param = self.spider['url'].get('param')

        if len(_param) == 1 and len(set(list(_param.items())[0])) == 1:
            param = list(_param.values())[0]
        else:
            param = dict_to_body(_param)

        return f'{protocol}://{domain}/{path}?{param}'.strip('?')

    @url.setter
    def url(self, url):
        self.spider['url'] = url_to_dict(url)

    @property
    def body(self):
        body = self.spider.get('body')
        return dict_to_body(body or {})

    @property
    def body_dict(self):
        return self.spider.get('body')

    @body.setter
    def body(self, body):
        self.spider['body'] = body_to_dict(body)

    @property
    def json(self):
        return dict_to_json(self.spider.get('json'))

    @property
    def json_dict(self):
        return self.spider.get('json')

    @json.setter
    def json(self, json):
        self.spider['json'] = json_to_dict(json)

    @property
    def headers(self):
        return self.spider.get('headers')

    @headers.setter
    def headers(self, headers):
        self.spider['headers'] = headers_to_dict(headers)

    @property
    def cookies(self):
        _cookies = self.cookie_jar
        return _cookies.get_dict() if _cookies else {}

    @cookies.setter
    def cookies(self, cookie):
        if isinstance(cookie, str): cookie = cookies_to_dict(cookie)

        self.spider['cookies'] = merge_cookies(self.spider.get('cookies'), cookie)

    @property
    def cookie_jar(self):
        return self.spider.get('cookies')

    def update(self, **kwargs):
        self.spider = update({key: value for key, value in kwargs.items()}, data=self.spider)

    def update_cookie_from_header(self):
        cookie = self.headers.get('Cookie')
        if cookie:
            cookie_dict = cookies_to_dict(cookie)
            self.spider['cookies'] = merge_cookies(self.spider.get('cookies'), cookie_dict)

    def update_cookie_from_resp(self, response):
        if hasattr(response, 'cookies'):
            self.spider['cookies'] = merge_cookies(self.spider.get('cookies'), response.cookies)

    def thread(self, url=None, callback=None, args=None, priority=None, **kwargs):

        if url: self.url = url
        return self.create_thread(
            url=self.url,
            method=self.method,
            data=self.body,
            json=self.json_dict,
            headers=self.headers,
            cookies=self.cookies,
            priority=priority,
            callback=callback,
            args=args,
            **kwargs
        )

    def create_thread(self, url=None, method=None, data=None, json=None, headers=None, cookies=None,
                      callback=None, args=None, priority=None, **kwargs):
        request_kwargs = {
            **self.request_kwargs,
            'url': url,
            'method': method or 'GET',
            'data': data or '',
            'json': json or {},
            'headers': headers or self.headers,
            'cookies': cookies,
            'priority': priority,
            'callback': callback,
            'args': args,
            **kwargs,
        }
        return RequestThread(**request_kwargs)

    def __repr__(self):
        msg = f'{type(self).__name__}({self.method}, url=\'{self.url}\', body=\'{self.body or self.json}\', headers={self.headers}, cookies={self.cookies})'
        return msg
