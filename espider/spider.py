import threading
import time
from collections.abc import Generator
from espider.default import *
from espider.network import Request, Downloader
import random
from requests.cookies import cookiejar_from_dict, merge_cookies
from espider.parser.response import Response
from espider.settings import Settings
from espider.utils import requests
from espider.utils.tools import url_to_dict, body_to_dict, json_to_dict, headers_to_dict, cookies_to_dict, dict_to_body, \
    dict_to_json, update, search, delete, strip, replace, random_list, human_time
from espider.middlewares import RequestFilter


class Spider(object):
    """
    更新 url，data，body，headers，cookies等参数，并创建请求线程
    """

    __custom_setting__ = {
        'max_thread': 10,
        'max_retry': 0
    }

    def __init__(
            self,
            url=None,
            method=None,
            data=None,
            json=None,
            headers=None,
            cookies=None,
            name=None,
            use_session=False,
            **kwargs
    ):
        self.name = name or self.__class__.__name__
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
        self.session = requests.Session()
        self.session.headers = self.spider.get('headers')

        # 加载 setting
        self.settings = Settings()
        self.settings.__dict__.update(self.__custom_setting__)

        # 加载 downloader setting
        self.downloader_setting = {k: v for k, v in self.settings.items() if k in Downloader.__settings__}
        self.request_setting = {k: v for k, v in self.settings.items() if k in Request.__settings__}

        self.downloader = Downloader(
            **self.downloader_setting,
            end_callback=self.end,
        )

        # 连接数据库
        self.db = None
        self.cursor = None

        # 额外参数
        self.pocket = {}

        # 数据处理工具
        self.search = search
        self.update = update
        self.replace = replace
        self.delete = delete
        self.strip = strip
        self.random_list = random_list

        # 网络
        self.get = requests.get
        self.post = requests.post

        # 时间计算
        self.start_time = time.time()

        # 请求优先级
        self._next_priority_index = 0
        self._callback_priority_map = {}

        # log
        self.show_request_detail = False

    @property
    def debug(self):
        return self.downloader._debug

    @debug.setter
    def debug(self, value):
        self.downloader._debug = value

    def load_request_filter(self, host='localhost', port=6379, set_key=None, timeout=None, priority=None, **kwargs):
        self.downloader.add_middleware(RequestFilter(
            host=host, port=port, set_key=set_key, timeout=timeout, priority=priority, **kwargs
        ))

    def load_setting(self, setting):
        assert isinstance(setting, Setting)
        self.downloader_setting = {k: v for k, v in setting.items() if k in Downloader.__settings__}
        self.request_setting = {k: v for k, v in setting.items() if k in Request.__settings__}
        self.downloader.__dict__.update(self.downloader_setting)

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
        body = self.spider.get('body')
        return dict_to_body(body) if body else None

    @property
    def body_dict(self):
        return self.spider.get('body', {})

    @body.setter
    def body(self, body):
        self.spider['body'] = body_to_dict(body)

    @property
    def json(self):
        js_data = self.spider.get('json')
        return dict_to_json(js_data) if js_data else None

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

    def update_spider(self, **kwargs):
        self.spider = update({key: value for key, value in kwargs.items()}, data=self.spider)

    def update_cookie_from_header(self):
        cookie = self.headers.get('Cookie')
        if cookie:
            cookie_dict = cookies_to_dict(cookie)
            self.spider['cookies'] = merge_cookies(self.spider.get('cookies'), cookie_dict)

    def update_cookie_from_resp(self, response):
        if hasattr(response, 'cookies'):
            self.spider['cookies'] = merge_cookies(self.spider.get('cookies'), response.cookies)

    def request(self, url=None, method=None, data=None, json=None, headers=None, cookies=None, callback=None,
                cb_args=None, cb_kwargs=None, priority=None, use_session=None, **kwargs):

        if use_session is None: use_session = self.use_session
        if not callback: callback = self.parse

        # 注册函数
        if callback.__name__ not in self._callback_priority_map.keys():
            self._callback_priority_map[callback.__name__] = self._next_priority_index
            self._next_priority_index += 1

        if not priority: priority = self._callback_priority_map.get(callback.__name__)

        request_kwargs = {
            **self.request_kwargs,
            'url': url or self.url,
            'method': method or 'GET',
            'data': data,
            'json': json,
            'headers': headers or self.headers,
            'cookies': cookies,
            'priority': priority,
            'callback': callback,
            'downloader': self.downloader,
            'cb_args': cb_args,
            'cb_kwargs': cb_kwargs,
            'session': self.session if use_session else None,
            'show_detail': self.show_request_detail,
            **self.request_setting,
            **kwargs,
        }
        return Request(**request_kwargs)

    def form_request(self, url=None, data=None, json=None, headers=None, cookies=None, callback=None, args=None,
                     kwarg=None, priority=None, use_session=False, **kwargs):

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
            kwarg=kwarg,
            priority=priority,
            use_session=use_session,
            **kwargs
        )

    def request_from_response(self, response):
        isinstance(response, Response)
        return self.request(**response.request_kwargs)

    def before(self):
        pass

    def start_requests(self):
        """
        入口
        """
        yield ...

    def run(self):
        self.before()

        if type(self.downloader).__name__ == 'type':
            self.downloader = self.downloader()

        spider_thread = threading.Thread(target=self._run)
        spider_thread.start()
        self.downloader.start()
        spider_thread.join()

    def _run(self):
        result = self.start_requests()
        if isinstance(result, Generator):
            for request in result:
                if isinstance(request, Request):
                    self.downloader.push(request)
                else:
                    print(f'Warning ... start_requests yield {request}, not a Request object')
        elif isinstance(result, Request):
            self.downloader.push(result)

    def parse(self, response, *args, **kwargs):
        pass

    def close(self):
        self.downloader._close = True

    def end(self):
        cost_time = human_time(time.time() - self.start_time - self.downloader.close_countdown)
        print('Time: {} day {} hour {} minute {:.3f} second'.format(*cost_time))
