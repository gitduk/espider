import time
from collections.abc import Generator
import requests
import threading
from queue import Queue
import urllib3
from copy import deepcopy
from espider.default_settings import REQUEST_KEYS, DEFAULT_METHOD_VALUE
from espider.parser.response import Response
from espider.utils.tools import args_split, PriorityQueue

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Request(threading.Thread):
    __settings__ = [
        'max_retry'
    ]
    __DEFAULT_THREAD_VALUE__ = [
        'name',
        'daemon'
    ]

    def __init__(self, url, method='', args=None, **kwargs):
        super().__init__()
        threading.Thread.__init__(self, name=kwargs.get('name'), daemon=kwargs.get('daemon'))

        # 必要参数
        self.url = url
        self.method = method.upper() or 'GET'
        self.downloader = kwargs.get('downloader')
        if type(self.downloader).__name__ == 'type': raise TypeError('downloader must be a Downloader instance')
        assert self.method in DEFAULT_METHOD_VALUE, f'Invalid method {method}'

        # 请求参数
        self.request_kwargs = {key: value for key, value in kwargs.items() if key in REQUEST_KEYS}
        if self.request_kwargs.get('data') or self.request_kwargs.get('json'): self.method = 'POST'

        # 自定义参数
        self.response = None
        self.priority = kwargs.get('priority') or 0
        self.max_retry = kwargs.get('max_retry') or 0
        self.callback = kwargs.get('callback')
        self.session = kwargs.get('session')
        self.retry_count = 0
        self.args = args or ()
        self.is_start = False
        self.success = False

    def run(self):
        self.is_start = True
        start = time.time()
        if self.session:
            assert isinstance(self.session, requests.sessions.Session)
            session_kwargs = {k: v for k, v in self.request_kwargs.items() if k != 'cookies'}
            response = self.session.request(method=self.method, url=self.url, **session_kwargs)
        else:
            response = requests.request(method=self.method, url=self.url, **self.request_kwargs)

        if response.status_code != 200 and self.retry_count < self.max_retry:
            self.retry_count += 1
            msg = f'Retry-{self.retry_count}: [{self.method.upper()}] {response.url} {response.request.body or ""} {response.status_code}'
            print(msg)
            self.run()
        else:
            if response.status_code == 200: self.success = True

            response_pro = Response(response)
            setattr(response_pro, 'cost_time', '{:.3f}'.format(time.time() - start))
            setattr(response_pro, 'retry_count', self.retry_count)
            self.response = response_pro

            if not isinstance(self.args, tuple): self.args = (self.args,)
            args, kwargs = args_split(deepcopy(self.args))
            if self.callback:
                generator = self.callback(response_pro, *args, **kwargs)
                if not isinstance(generator, Generator):
                    raise TypeError(f'{self.callback.__name__} must be a generator')
                for _ in generator:
                    if isinstance(_, Request):
                        self.downloader.push(_)
                    elif isinstance(_, (dict, tuple)):
                        self.downloader.push_item(_)
                    else:
                        raise TypeError(f'{self.callback.__name__} must yield a dict or a Request object')

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__, self.name, self.priority)


class Downloader(object):
    __settings__ = ['wait_time', 'max_thread', 'extensions']

    def __init__(self, max_thread=None, wait_time=0, callback=None):
        self.thread_pool = PriorityQueue()
        self.item_pool = Queue()
        self.callback = callback
        self.max_thread = max_thread or 10
        self.running_thread = Queue()
        self.count = {'Success': 0, 'Retry': 0, 'Failed': 0}
        self.extensions = []
        self.wait_time = wait_time

    def push(self, request):
        assert isinstance(request, Request), f'task must be {type(Request)}'
        self.thread_pool.push(request, request.priority)

    def push_item(self, item):
        self.item_pool.put(item)

    def add_extension(self, extension, *args, **kwargs):
        if type(extension).__name__ == 'type':
            extension = extension()

        self.extensions.append(
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
            if self.thread_pool.empty() and self.running_thread.empty() and self.item_pool.empty():
                finish = True
            else:
                finish = False

        return finish

    def distribute_task(self):
        while not self._finish():
            if self.max_thread and threading.active_count() > self.max_thread:
                request = None
                self._join_thread()
            else:
                try:
                    request = self.thread_pool.pop()
                except IndexError:
                    self._join_thread()
                    print('Waiting task ...')
                    time.sleep(1)
                    continue

            if request:
                yield self._start_request(request)

            item = self.item_pool.get_nowait()
            if item:
                item, args, kwargs = self._process_callback_args(item)
                yield self.callback(item, *args, **kwargs)

        msg = f'All task is done. Success:{self.count.get("Success")}, Retry: {self.count.get("Retry")}, Failed: {self.count.get("Failed")}'
        print(msg)

    def start(self):
        for _ in self.distribute_task():
            if self._finish(): break

    @staticmethod
    def _process_callback_args(args):
        if isinstance(args, dict):
            return args, (), {}
        elif isinstance(args, tuple):
            data = args[0]
            assert isinstance(data, dict), 'yield item, args, kwargs,  item be a dict'
            args, kwargs = args_split(args[1:])
            return data, args, kwargs
        else:
            raise TypeError(f'Invalid item {args}, yield item, args, kwargs')

    def _start_request(self, request):
        assert isinstance(request, Request)

        if self.extensions:
            for _ in self.extensions:
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
            time.sleep(self.wait_time + request.retry_count * 0.1)
            if not request.is_start: request.start()
            self.running_thread.put(request)

    def _join_thread(self):
        while not self.running_thread.empty():
            request = self.running_thread.get()
            request.join()
            if request.success:
                self.count['Success'] += 1
                self.count['Retry'] += request.retry_count
            else:
                self.count['Failed'] += 1


def call(response):
    yield {'name': 'hi'}


d = Downloader()
url = 'https://blog.csdn.net/qq_43593912/article/details/97123701'
re = Request(url, callback=call, downloader=d)
re.start()
print(d.item_pool.get())
