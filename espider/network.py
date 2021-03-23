import requests
from espider.parser.response import Response
import threading
from queue import Queue
import logging
import random
import urllib3
from requests.cookies import cookiejar_from_dict, merge_cookies
from requests.sessions import Session
from espider.utils.tools import *
from espider.settings import USER_AGENT_LIST, __REQUEST_KEYS__

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class Request(threading.Thread):
    __DEFAULT_THREAD_VALUE__ = [
        'name',
        'daemon'
    ]

    __DEFAULT_METHOD_VALUE__ = [
        'GET',
        'POST',
        'HEAD',
        'OPTIONS',
        'PUT',
        'PATCH',
        'DELETE'
    ]

    def __init__(self, url, method='', args=None, **kwargs):
        super().__init__()
        threading.Thread.__init__(self, name=kwargs.get('name'), daemon=kwargs.get('daemon'))

        # 必要参数
        self.url = url
        self.method = method.upper() or 'GET'
        assert self.method in self.__DEFAULT_METHOD_VALUE__, f'Invalid method {method}'

        # 请求参数
        self.request_kwargs = {key: value for key, value in kwargs.items() if key in __REQUEST_KEYS__}
        if self.request_kwargs.get('data') or self.request_kwargs.get('json'): self.method = 'POST'

        # 自定义参数
        self.response = None
        self.priority = kwargs.get('priority') or 0
        self.max_retry = kwargs.get('max_retry') or 0
        self.callback = kwargs.get('callback')
        self.session = kwargs.get('session')
        self.retry_count = 0
        self.args = args or ()

    def run(self):
        if self.session:
            assert isinstance(self.session, requests.sessions.Session)
            session_kwargs = {k: v for k, v in self.request_kwargs.items() if k != 'cookies'}
            response = self.session.request(method=self.method, url=self.url, **session_kwargs)
        else:
            response = requests.request(method=self.method, url=self.url, **self.request_kwargs)

        if response.status_code != 200 and self.max_retry > 0:
            self.max_retry -= 1
            self.run()
            self.retry_count += 1
            msg = f'Retry-{self.priority}: [{self.method.upper()}] {response.url} {response.request.body or ""} {response.status_code}'
            print(msg)
        else:
            response_pro = Response(response)
            self.response = response_pro

            if not isinstance(self.args, tuple): self.args = (self.args,)
            args, kwargs = args_split(self.args)
            if self.callback: self.callback(response_pro, *args, **kwargs)

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__, self.name, self.priority)


class BaseSpider(object):
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
            if key in __REQUEST_KEYS__ and key not in self.spider.keys():
                self.request_kwargs[key] = value

        self.use_session = use_session
        self.session = Session() if self.use_session else None

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

    def request(self, url=None, callback=None, args=None, priority=None, **kwargs):

        if url: self.url = url
        return self.new_request(
            url=self.url,
            method=self.method,
            data=self.body,
            json=self.json_dict,
            headers=self.headers,
            cookies=self.cookies,
            use_session=self.use_session,
            priority=priority,
            callback=callback,
            args=args,
            **kwargs
        )

    def new_request(self, url=None, method=None, data=None, json=None, headers=None, cookies=None,
                    callback=None, args=None, priority=None, use_session=False, **kwargs):
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
            'session': self.session if use_session else None,
            **kwargs,
        }
        return Request(**request_kwargs)

    def __repr__(self):
        msg = f'{type(self).__name__}({self.method}, url=\'{self.url}\', body=\'{self.body or self.json}\', headers={self.headers}, cookies={self.cookies})'
        return msg


class Downloader(object):
    def __init__(self, max_thread=None, wait_time=0):
        self.thread_pool = PriorityQueue()
        self.max_thread = max_thread
        self.running_thread = Queue()
        self.download_number = 0
        self._extensions = []
        self.wait_time = wait_time

    def push(self, request):
        assert isinstance(request, Request), f'task must be {type(Request)}'
        self.thread_pool.push(request, request.priority)

    def add_extension(self, extension, *args, **kwargs):
        if type(extension).__name__ == 'type':
            extension = extension()

        self._extensions.append(
            {
                'extension': extension,
                'args': args,
                'kwargs': kwargs,
                'count': 0
            }
        )

    def _finish(self):
        finish = False
        for i in range(3):
            if self.thread_pool.empty():
                finish = True
            else:
                finish = False

        return finish

    def start(self):
        while not self._finish():
            if self.max_thread and threading.active_count() > self.max_thread:
                request = None
                self._join_thread()
            else:
                request = self.thread_pool.pop()

            if request:
                assert isinstance(request, Request)

                if self._extensions:
                    for _ in self._extensions:
                        extension, args, kwargs = _.get('extension'), _.get('args'), _.get('kwargs')
                        if request:
                            if args and kwargs:
                                request = extension(request, *args, **kwargs)
                            elif args:
                                request = extension(request, *args)
                            elif kwargs:
                                request = extension(request, **kwargs)
                            else:
                                request = extension(request)

                            _['count'] += 1

                    assert isinstance(
                        request, Request
                    ) or not request, 'Extensions must return RequestThread or None'

                if request:
                    print(request.url)
                    time.sleep(self.wait_time + request.retry_count * 0.1)
                    if not request.is_alive(): request.start()
                    self.running_thread.put(request)
                    self.download_number += 1

        if not self.running_thread.empty():
            self._join_thread()

        for i in range(1, 4):
            print(f'Waiting task ... {4 - i}')
            time.sleep(1)
            # if not self._finish():
            #     self.start()

        print(f'All task is done, download count:{self.download_number}')

    def _join_thread(self):
        while not self.running_thread.empty():
            request = self.running_thread.get()
            request.join()
