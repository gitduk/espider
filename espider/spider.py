import threading
import random
import time
from collections.abc import Generator
from espider.network import Request, Downloader
from espider.parser.response import Response
from espider.settings import Settings, USER_AGENT_LIST
from espider.utils import requests
from espider.utils.tools import human_time


class Spider(object):
    """
    更新 url，data，body，headers，cookies等参数，并创建请求线程
    """

    __custom_setting__ = {
        'request': {
            'max_retry': 0,
            'timeout': None
        },
        'download': {
            'max_thread': 1,
            'wait_time': 0,
            'close_countdown': 3,
            'distribute_item': True
        }
    }

    def __init__(
            self,
            name=None,
            use_session=False,
    ):
        self.name = name or self.__class__.__name__

        self.use_session = use_session

        if use_session:
            self.session = requests.Session()
            self.session.headers = {'User-Agent': random.choice(USER_AGENT_LIST)}

        # 加载 setting
        self.settings = Settings(self.__custom_setting__)
        self.request_setting = {k: v for k, v in self.settings.request.__dict__.items()}

        self.downloader = Downloader(
            **{k: v for k, v in self.settings.downloader.__dict__.items()},
            end_callback=self.end,
        )

        # 时间计算
        self.start_time = time.time()

        # 请求优先级
        self._next_priority_index = 0
        self._callback_priority_map = {}

        # log
        self.show_request_detail = False

        self.prepare()

    def request(self, url=None, method=None, data=None, json=None, headers=None, cookies=None, callback=None,
                cb_args=None, cb_kwargs=None, priority=None, use_session=None, **kwargs):

        if use_session is None: use_session = self.use_session
        if not callback: callback = self.parse

        # 注册函数
        if callback.__name__ not in self._callback_priority_map.keys():
            self._callback_priority_map[callback.__name__] = self._next_priority_index
            self._next_priority_index += 1

        if not priority: priority = self._callback_priority_map.get(callback.__name__)

        if not headers and hasattr(self, 'headers'): headers = self.headers
        if not cookies and hasattr(self, 'cookies'): cookies = self.cookies

        request_kwargs = {
            **self.request_setting,
            'url': url,
            'method': method or 'GET',
            'data': data,
            'json': json,
            'headers': headers or {'User-Agent': random.choice(USER_AGENT_LIST)},
            'cookies': cookies,
            'priority': priority,
            'callback': callback,
            'downloader': self.downloader,
            'cb_args': cb_args,
            'cb_kwargs': cb_kwargs,
            'session': self.session if use_session else None,
            'show_detail': self.show_request_detail,
            **kwargs,
        }
        return Request(**request_kwargs)

    def form_request(self, url=None, data=None, json=None, headers=None, cookies=None, callback=None, cb_args=None,
                     cb_kwargs=None, priority=None, use_session=False, **kwargs):

        return self.request(
            self,
            url=url,
            method='POST',
            data=data,
            json=json,
            headers=headers,
            cookies=cookies,
            callback=callback,
            cb_args=cb_args,
            cb_kwargs=cb_kwargs,
            priority=priority,
            use_session=use_session,
            **kwargs
        )

    def request_from_response(self, response):
        isinstance(response, Response)
        return self.request(**response.request_kwargs)

    def prepare(self, *args, **kwargs):
        pass

    def start_requests(self, *args, **kwargs):
        """
        入口
        """
        yield ...

    def start(self, *args, **kwargs):

        if type(self.downloader).__name__ == 'type':
            self.downloader = self.downloader()

        spider_thread = threading.Thread(target=self._run, args=args, kwargs=kwargs)
        spider_thread.start()
        self.downloader.start()
        spider_thread.join()

    def run(self, *args, **kwargs):
        self.start(*args, **kwargs)

    def _run(self, *args, **kwargs):
        result = self.start_requests(*args, **kwargs)
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
