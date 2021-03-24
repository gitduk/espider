from espider.default_settings import *
from espider.network import Request, Downloader
import random
from requests.cookies import cookiejar_from_dict, merge_cookies
from requests.sessions import Session
from espider.parser.response import Response

from espider.settings import Setting
from espider.utils.tools import url_to_dict, body_to_dict, json_to_dict, headers_to_dict, cookies_to_dict, dict_to_body, \
    dict_to_json, update


class Spider(object):
    """
    更新 url，data，body，headers，cookies等参数，并创建请求线程
    """

    __custom_setting__ = {
        'downloader': {
            'max_thread': 10
        },
        'request': {
            'max_retry': 3
        }
    }

    def __init__(
            self,
            url=None,
            method=None,
            data=None,
            json=None,
            headers=None,
            cookies=None,
            use_session=False,
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
            if key in REQUEST_KEYS and key not in self.spider.keys():
                self.request_kwargs[key] = value

        self.use_session = use_session
        self.session = Session() if self.use_session else None

        # 加载 setting
        self.setting = Setting()
        self.setting.__dict__.update(self.__custom_setting__)

        # 加载 downloader setting
        self.downloader_setting = self.setting.get('downloader') if self.setting.get('downloader') else {}
        self.request_setting = self.setting.get('request') if self.setting.get('request') else {}

        self.downloader = Downloader(
            **self.downloader_setting,
            item_callback=self.item_pipeline,
            response_callback=self.response_pipeline,
            request_callback=self.request_pipeline
        )

    def _init_header(self):
        if self.method == 'POST':
            content_type = 'application/x-www-form-urlencoded; charset=UTF-8'
            if self.spider.get('json'): content_type = 'application/json; charset=UTF-8'
            return {'User-Agent': random.choice(USER_AGENT_LIST), 'Content-Type': content_type}
        else:
            return {'User-Agent': random.choice(USER_AGENT_LIST)}

    @property
    def url(self):
        if self.spider['url']:
            protocol = self.spider['url'].get('protocol')
            domain = self.spider['url'].get('domain')
            path = '/'.join(self.spider['url'].get('path'))
            _param = self.spider['url'].get('param')

            if len(_param) == 1 and len(set(list(_param.items())[0])) == 1:
                param = list(_param.values())[0]
            else:
                param = dict_to_body(_param)

            return f'{protocol}://{domain}/{path}?{param}'.strip('?')
        else:
            return ''

    @url.setter
    def url(self, url):
        self.spider['url'] = url_to_dict(url)

    @property
    def body(self):
        body = self.spider.get('body', {})
        return dict_to_body(body)

    @property
    def body_dict(self):
        return self.spider.get('body', {})

    @body.setter
    def body(self, body):
        self.spider['body'] = body_to_dict(body)

    @property
    def json(self):
        return dict_to_json(self.spider.get('json', {}))

    @property
    def json_dict(self):
        return self.spider.get('json', {})

    @json.setter
    def json(self, json):
        self.spider['json'] = json_to_dict(json)

    @property
    def headers(self):
        return self.spider.get('headers', {})

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

    def request(self, url=None, method=None, data=None, json=None, headers=None, cookies=None, callback=None, args=None,
                priority=None, use_session=False, **kwargs):

        request_kwargs = {
            **self.request_kwargs,
            'url': url or self.url,
            'method': method or 'GET',
            'data': data or '',
            'json': json or {},
            'headers': headers or self.headers,
            'cookies': cookies,
            'priority': priority,
            'callback': callback or self.parse,
            'downloader': self.downloader,
            'args': args,
            'session': self.session if use_session else None,
            **self.request_setting,
            **kwargs,
        }
        return Request(**request_kwargs)

    def form_request(self, url=None, data=None, json=None, headers=None, cookies=None, callback=None, args=None,
                     priority=None, use_session=False, **kwargs):

        return self.request(
            self,
            url=url,
            method='POST',
            data=data,
            json=json,
            headers=headers,
            cookies=cookies,
            callback=callback,
            args=args,
            priority=priority,
            use_session=use_session,
            **kwargs
        )

    def request_from_response(self, response):
        isinstance(response, Response)
        return self.request(**response.request_kwargs)

    @staticmethod
    def start_requests():
        """
        起点
        """
        yield ...

    def run(self):
        if type(self.downloader).__name__ == 'type':
            self.downloader = self.downloader()

        for request in self.start_requests():
            self.downloader.push(request)

        self.downloader.start()

    def parse(self, response, *args, **kwargs):
        pass

    def item_pipeline(self, item, *args, **kwargs):
        pass

    def response_pipeline(self, response, *args, **kwargs):
        pass

    def request_pipeline(self, request, *args, **kwargs):
        pass

    def __repr__(self):
        msg = f'{type(self).__name__}({self.method}, url=\'{self.url}\', body=\'{self.body or self.json}\', headers={self.headers}, cookies={self.cookies})'
        return msg
